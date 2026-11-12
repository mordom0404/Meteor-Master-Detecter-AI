VERSION = "2.5.0"

import os
import sys

import onnxruntime as ort  # noqa: E402
import numpy as np  # noqa: E402
# Workaround for Nuitka onefile + cv2: cv2/__init__.py's bootstrap() calls
# importlib.import_module("cv2") which recurses through Nuitka's compiled-module hook
# and crashes with "recursion is detected during loading of cv2 binary extensions".
# cv2.pyd already exposes everything we need (cv2.imread, cv2.dnn.NMSBoxes, etc.)
# as built-in submodules - skip __init__.py entirely and load cv2.pyd as cv2.
def _load_cv2_bypass():
    import importlib.util
    pyd_path = None
    for p in sys.path:
        if not p:
            continue
        cand = os.path.join(p, "cv2.pyd")
        if os.path.isfile(cand):
            pyd_path = cand
            break
        cand2 = os.path.join(p, "cv2", "cv2.pyd")
        if os.path.isfile(cand2):
            pyd_path = cand2
            break
    if not pyd_path:
        # Nuitka onefile quirk: sys.path at module-import time doesn't yet include
        # the onefile temp dir that holds cv2.pyd. cv2's own bootstrap adds it
        # at line 132-133, but only after we've already started importing cv2
        # (causing recursion). So: let the normal import run, catch the recursion,
        # then re-load from the now-populated sys.path.
        try:
            import cv2 as _cv2_normal
            return _cv2_normal
        except ImportError:
            # sys.path now has the onefile temp dir (cv2's bootstrap added it
            # before the recursion guard fired). Retry the search.
            for p in sys.path:
                if not p:
                    continue
                cand = os.path.join(p, "cv2.pyd")
                if os.path.isfile(cand):
                    pyd_path = cand
                    break
                cand2 = os.path.join(p, "cv2", "cv2.pyd")
                if os.path.isfile(cand2):
                    pyd_path = cand2
                    break
            if not pyd_path:
                raise RuntimeError(
                    "cv2.pyd not found in sys.path even after cv2 bootstrap tried. "
                    "This shouldn't happen with a properly bundled Nuitka onefile exe."
                )
    spec = importlib.util.spec_from_file_location("cv2", pyd_path)
    cv2_mod = importlib.util.module_from_spec(spec)
    sys.modules["cv2"] = cv2_mod
    spec.loader.exec_module(cv2_mod)
    return cv2_mod

cv2 = _load_cv2_bypass()  # noqa: E402

import argparse
import json
import queue
import threading
import time
import uuid
from PIL import Image
from PIL.ExifTags import TAGS

# Watch mode dependency. If watchdog is missing, --help still works but
# --watch_folder fails with a clear error instead of an import traceback.
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG_AVAILABLE = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    _WATCHDOG_AVAILABLE = False

CLASSES = ["meteor", "plane", "sprite", "lightning"]

NOTICES_FILENAME = "THIRD_PARTY_NOTICES.md"
NOTICES_URL = (
    "https://github.com/mordom0404/Meteor-Master-Detecter-AI/blob/master/"
    "THIRD_PARTY_NOTICES.md"
)


def _read_third_party_notices():
    """读取第三方许可清单。

    Nuitka onefile 会把 THIRD_PARTY_NOTICES.md 解压到临时目录，源码运行时则
    直接读仓库根目录，所以按 __file__ / argv[0] / cwd 依次找。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [here, os.path.dirname(os.path.abspath(sys.argv[0])), os.getcwd()]
    for directory in candidates:
        path = os.path.join(directory, NOTICES_FILENAME)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    return handle.read()
            except OSError:
                continue
    return None


def print_third_party_notices():
    """`--licenses`：打印随程序分发的第三方组件许可信息。"""
    text = _read_third_party_notices()
    # 许可清单是 UTF-8 中文/英文混排；在非中文 Windows（管道默认用 ANSI 代码页）
    # 上直接 print 可能 UnicodeEncodeError，这里显式按 UTF-8 输出。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if text:
        print(text)
        return
    print("本程序包含第三方开源组件，完整许可信息见：")
    print(NOTICES_URL)


class YOLOv8:
    """ONNX Runtime 推理封装：模型加载、预处理、后处理与坐标换算。"""

    def __init__(self, onnx_path, force_CPU):
        """创建推理会话（模型路径错误会直接抛 onnxruntime 的异常）。

        Args:
            onnx_path: ONNX 模型文件路径。
            force_CPU: 为 True 时强制使用 CPUExecutionProvider。
        """
        # 置信度阈值；iou_thres 为 0 表示不对重叠框做抑制
        self.confidence_thres = 0.5
        self.iou_thres = 0

        """Initialize onnxruntime with filtered providers."""
        available_providers = ort.get_available_providers()
        options = ort.SessionOptions()
        options.enable_profiling = False

        # Filter available providers to ones we can actually use:
        # - Windows: DirectML (DmlExecutionProvider, requires DX12 + compatible GPU)
        #   and CPU fallback. TensorRT/CUDA EPs being listed in available_providers
        #   does NOT mean we can use them (need CUDA + cuBLAS + TensorRT native libs);
        #   printing them as if supported misleads users.
        # - macOS: CoreML + CPU fallback.
        if os.name == "nt":
            if force_CPU:
                providers = ["CPUExecutionProvider"]
            else:
                preferred = ["DmlExecutionProvider", "CPUExecutionProvider"]
                providers = [p for p in preferred if p in available_providers]
                if not providers:
                    providers = ["CPUExecutionProvider"]
        else:
            preferred = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
            providers = [p for p in preferred if p in available_providers]
            if not providers:
                providers = ["CPUExecutionProvider"]

        print("providers: active=", providers, "force_CPU=", force_CPU, flush=True)
        self.onnx_session = ort.InferenceSession(onnx_path, providers=providers)

    def rotate_image_45(self, image):
        """
        将图像旋转45度
        """
        # 获取图像中心点
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)

        # 创建旋转矩阵，旋转45度
        rotation_matrix = cv2.getRotationMatrix2D(center, 45, 1.0)

        # 计算旋转后图像的边界框
        cos = np.abs(rotation_matrix[0, 0])
        sin = np.abs(rotation_matrix[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))

        # 调整旋转矩阵的平移部分，使图像居中
        rotation_matrix[0, 2] += (new_w / 2) - center[0]
        rotation_matrix[1, 2] += (new_h / 2) - center[1]

        # 执行旋转
        rotated = cv2.warpAffine(image, rotation_matrix, (new_w, new_h))

        return rotated, rotation_matrix, new_w, new_h

    def transform_coordinates_back(self, boxes, transform_info):
        """
        将检测框坐标从2048x2048推理画布变换回最终的2048x2048显示画布
        """
        if len(boxes) == 0:
            return boxes

        transformed_boxes = []

        # 获取变换信息
        original_width = transform_info["original_width"]
        original_height = transform_info["original_height"]
        scale = transform_info["scale"]
        rotation_matrix = transform_info["rotation_matrix"]
        canvas_scale = transform_info["canvas_scale"]

        for box in boxes:
            x1, y1, x2, y2, score, class_id = box

            # 第1步：从2048x2048推理画布坐标转换到旋转后图像坐标
            if rotation_matrix is not None:
                # 计算旋转后图像在2048画布中的偏移
                rotated_width = transform_info["rotated_width"]
                rotated_height = transform_info["rotated_height"]
                scaled_rot_w = rotated_width * canvas_scale
                scaled_rot_h = rotated_height * canvas_scale
                rot_offset_x = (2048 - scaled_rot_w) // 2
                rot_offset_y = (2048 - scaled_rot_h) // 2

                # 转换到旋转图像坐标系
                rot_x1 = (x1 - rot_offset_x) / canvas_scale
                rot_y1 = (y1 - rot_offset_y) / canvas_scale
                rot_x2 = (x2 - rot_offset_x) / canvas_scale
                rot_y2 = (y2 - rot_offset_y) / canvas_scale

                # 第2步：计算检测框中心点并应用逆旋转
                center_x = (rot_x1 + rot_x2) / 2
                center_y = (rot_y1 + rot_y2) / 2
                width = rot_x2 - rot_x1
                height = rot_y2 - rot_y1

                # 应用逆旋转变换
                inverse_rotation_matrix = cv2.invertAffineTransform(rotation_matrix)
                center_point = np.array([center_x, center_y, 1])
                orig_center = inverse_rotation_matrix @ center_point

                # 第3步：转换回原始图像坐标系
                orig_center_x = orig_center[0] / scale
                orig_center_y = orig_center[1] / scale
                orig_width = width / scale
                orig_height = height / scale

            else:
                # 没有旋转的情况
                # 计算原始图像在2048画布中的偏移
                scaled_w = original_width * scale
                scaled_h = original_height * scale
                offset_x = (2048 - scaled_w) // 2
                offset_y = (2048 - scaled_h) // 2

                # 转换到原始图像坐标系
                orig_x1 = (x1 - offset_x) / scale
                orig_y1 = (y1 - offset_y) / scale
                orig_x2 = (x2 - offset_x) / scale
                orig_y2 = (y2 - offset_y) / scale

                orig_center_x = (orig_x1 + orig_x2) / 2
                orig_center_y = (orig_y1 + orig_y2) / 2
                orig_width = orig_x2 - orig_x1
                orig_height = orig_y2 - orig_y1

            # 第4步：映射到2048x2048最终显示画布
            # 假设原始图像在2048x2048画布中居中显示
            final_scale = min(2048.0 / original_width, 2048.0 / original_height)
            final_width = original_width * final_scale
            final_height = original_height * final_scale
            final_offset_x = (2048 - final_width) // 2
            final_offset_y = (2048 - final_height) // 2

            # 计算最终坐标
            final_center_x = orig_center_x * final_scale + final_offset_x
            final_center_y = orig_center_y * final_scale + final_offset_y
            final_box_width = orig_width * final_scale
            final_box_height = orig_height * final_scale

            final_x1 = final_center_x - final_box_width / 2
            final_y1 = final_center_y - final_box_height / 2
            final_x2 = final_center_x + final_box_width / 2
            final_y2 = final_center_y + final_box_height / 2

            # 确保坐标在2048x2048范围内
            final_x1 = max(0, min(2048, final_x1))
            final_y1 = max(0, min(2048, final_y1))
            final_x2 = max(0, min(2048, final_x2))
            final_y2 = max(0, min(2048, final_y2))

            transformed_boxes.append([final_x1, final_y1, final_x2, final_y2, score, class_id])

        return transformed_boxes

    def preprocess(self, img, mask_path, rotate=False):
        """1.cv2读取图像并resize
        2.图像转BGR2RGB和HWC2CHW(因为yolov5的onnx模型输入为 RGB：1 × 3 × 2048 × 2048)
        3.图像归一化
        4.图像增加维度
        5.onnx_session 推理"""

        # 缩放原图到长边2048
        original_height, original_width = img.shape[:2]
        desired_size = 2048
        max_dimension = max(original_height, original_width)

        # 计算缩放比例
        scale = float(desired_size) / float(max_dimension)
        new_width = int(scale * original_width)
        new_height = int(scale * original_height)

        # 缩放图像并保持长宽比
        img = cv2.resize(img, (new_width, new_height))
        masked_image = img

        if mask_path != "":
            mask_image = cv2.imdecode(np.fromfile(mask_path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            # 调整蒙版图像的大小，使其与原始图像相匹配
            mask_image = cv2.resize(mask_image, (img.shape[1], img.shape[0]))
            # 提取蒙版图像的 alpha 通道
            alpha_channel = mask_image[:, :, 3]
            # 使用 alpha 通道创建一个反转蒙版，将不透明的部分设为黑色，透明的部分设为白色
            invert_mask = cv2.cvtColor(cv2.bitwise_not(alpha_channel), cv2.COLOR_GRAY2BGR)
            invert_mask[np.where(invert_mask != 0)] = 255

            # 执行按位与操作，删除蒙版区域的原始图像像素
            masked_image = cv2.bitwise_and(img, invert_mask)

        # 存储变换信息用于坐标转换
        transform_info = {"original_width": original_width, "original_height": original_height, "scale": scale, "rotation_matrix": None, "rotated_width": None, "rotated_height": None, "canvas_scale": 1.0}

        # 如果需要旋转，先旋转图像
        if rotate:
            masked_image, rotation_matrix, rot_w, rot_h = self.rotate_image_45(masked_image)
            transform_info["rotation_matrix"] = rotation_matrix
            transform_info["rotated_width"] = rot_w
            transform_info["rotated_height"] = rot_h

            # 重新计算缩放比例以适应2048x2048画布
            max_rot_dimension = max(rot_h, rot_w)
            canvas_scale = float(desired_size) / float(max_rot_dimension)
            if canvas_scale < 1.0:  # 只在需要缩小时才缩放
                masked_image = cv2.resize(masked_image, (int(rot_w * canvas_scale), int(rot_h * canvas_scale)))
                transform_info["canvas_scale"] = canvas_scale
            else:
                transform_info["canvas_scale"] = 1.0

        # 创建一个2048x2048的黑色背景画布
        canvas = np.zeros((desired_size, desired_size, 3), dtype=np.uint8)

        # 计算图像在画布中的位置
        x_start = (desired_size - masked_image.shape[1]) // 2
        y_start = (desired_size - masked_image.shape[0]) // 2

        # 在画布的对应位置绘制图像
        canvas[y_start : y_start + masked_image.shape[0], x_start : x_start + masked_image.shape[1]] = masked_image

        or_img = canvas
        img = or_img[:, :, ::-1].transpose(2, 0, 1)  # BGR2RGB和HWC2CHW
        img = img.astype(dtype=np.float32)  # onnx模型的类型是type: float32[ , , , ]
        img /= 255.0
        img = np.expand_dims(img, axis=0)  # [3, 2048, 2048]扩展为[1, 3, 2048, 2048]

        # 返回：模型输入张量、画布图像、坐标换算信息
        return img, or_img, transform_info

    def postprocess(self, input_image, output):
        """把模型原始输出解码成检测框，并按流星长轴方向修正角点。

        模型输出布局为 ``(1, N, 4 + 类别数)``：每行前 4 个数是框中心点与宽高
        （单位是 2048×2048 画布坐标），之后是各类别分数。

        Args:
            input_image: 与画布同坐标系的图像，用于判断流星走向。
            output: onnxruntime 的原始输出数组。

        Returns:
            list: 每项为 ``[x1, y1, x2, y2, score, class_id]``。
        """
        # (1, N, 4+类别数) -> (N, 4+类别数)，一行一个候选框
        rows = np.squeeze(output[0]).T

        boxes, scores, class_ids = [], [], []

        for row in rows:
            per_class = row[4:]
            best = np.amax(per_class)
            if best < self.confidence_thres:
                continue

            # row 前 4 项为 (中心 x, 中心 y, 宽, 高)，换算成左上角坐标
            x, y, w, h = row[0], row[1], row[2], row[3]
            left = int(x - w / 2)
            top = int(y - h / 2)
            width = int(w)
            height = int(h)

            boxes.append([left, top, width, height])
            scores.append(best)
            class_ids.append(np.argmax(per_class))

        # 同一目标可能留下多个候选框，按 IoU 阈值做非极大值抑制
        kept = cv2.dnn.NMSBoxes(boxes, scores, self.confidence_thres, self.iou_thres)

        detections = []
        for idx in kept:
            left, top, width, height = boxes[idx]
            detections.append([left, top, left + width, top + height, scores[idx], class_ids[idx]])

        # 角点切换：direction == 1（右上-左下）时交换 x1/x2
        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det[:4]
            roi = input_image[int(y1) : int(y2), int(x1) : int(x2)]
            direction = self.determine_meteor_direction(roi)
            print(f"Box {i} direction: {direction}")
            if direction == 1:
                detections[i] = [x2, y1, x1, y2] + det[4:]

        return detections

    def calc_roi_gradient(self, img, mask=None):
        """
        计算图像区域的梯度方向
        :param img: 输入图像
        :param mask: 可选的掩码
        :return: 平均梯度角度（弧度）
        """
        if img.ndim == 3 and img.shape[-1] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)  # dI/dx
        gy = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)  # dI/dy
        Ia = np.arctan2(-gy, gx) % np.pi
        weight = np.hypot(gx, gy)
        if mask is not None:
            weight = weight * (mask.astype(weight.dtype))
        else:
            high_weight = np.percentile(weight, 95)
            weight = weight * (weight > high_weight)
        sum_weight = np.sum(weight)
        if sum_weight == 0:
            return float("nan")
        complex_sum = np.sum(weight * np.exp(1j * Ia))
        mean_angle = np.angle(complex_sum / sum_weight)
        return float(mean_angle % (2 * np.pi))

    def determine_meteor_direction(self, meteor_image):
        """
        判断流星飞行方向
        :param meteor_image: 流星区域图像
        :return: 飞行方向 (0 - 左上到右下, 1 - 右上到左下)
        """
        height, width = meteor_image.shape[:2]

        # 确保图像尺寸足够大
        if height < 10 or width < 10:
            # print(f"Warning: meteor_image too small: {width}x{height}")
            return 0  # 默认返回一个方向

        # 计算整个流星区域的梯度方向
        angle = self.calc_roi_gradient(meteor_image)

        # 将角度转换为度数
        angle_deg = np.degrees(angle)

        # 判断方向：
        # 与x轴夹角在0-90度或180-270度范围内为左上到右下(0)
        # 其他角度范围为右上到左下(1)
        if (0 <= angle_deg <= 90) or (180 <= angle_deg <= 270):
            return 0  # 左上到右下
        else:
            return 1  # 右上到左下

    # def calculate_brightness(self, image):
    #     """
    #     计算图像的亮度
    #     :param image: 输入图像
    #     :return: 图像的亮度值
    #     """
    #     # 将图像转为灰度
    #     gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    #     # 计算平均亮度
    #     return np.mean(gray_image)

    # def determine_meteor_direction(self, meteor_image):
    #     """
    #     判断流星飞行方向
    #     :param meteor_image: 流星区域图像
    #     :param width_ratio: 矩形区域相对于图像宽度的比例
    #     :param height_ratio: 矩形区域相对于图像高度的比例
    #     :return: 飞行方向 (0 - 左上到右下, 1 - 右上到左下)
    #     """
    #     height, width = meteor_image.shape[:2]

    #     # 确保图像尺寸足够大
    #     if height < 10 or width < 10:
    #         print(f"Warning: meteor_image too small: {width}x{height}")
    #         return 0  # 默认返回一个方向

    #     # 计算提取区域大小
    #     extract_width = int(width * 0.1)
    #     extract_height = int(height * 0.1)

    #     # 确保提取区域至少为1像素
    #     extract_width = max(1, extract_width)
    #     extract_height = max(1, extract_height)

    #     # 提取左上到右下对角线附近的矩形区域
    #     left_top_to_right_bottom = meteor_image[0:extract_height, 0:extract_width]
    #     brightness_left_to_right = self.calculate_brightness(left_top_to_right_bottom)

    #     # 提取右上到左下对角线附近的矩形区域
    #     right_top_to_left_bottom = meteor_image[0:extract_height, width - extract_width : width]
    #     brightness_right_to_left = self.calculate_brightness(right_top_to_left_bottom)

    #     # 根据亮度判断方向
    #     return 0 if brightness_left_to_right > brightness_right_to_left else 1

    def inference(self, img, mask_path, debug):
        """
        Performs inference using an ONNX model and returns the output image with drawn detections.
        如果第一次检测没有结果，会旋转45度再次检测。

        Returns:
            output_img: The output image with drawn detections.
        """

        # Get the model inputs
        model_inputs = self.onnx_session.get_inputs()

        # 第一次检测（不旋转）
        img_data, or_img, transform_info = self.preprocess(img, mask_path, rotate=False)
        outputs = self.onnx_session.run(None, {model_inputs[0].name: img_data})
        pred = self.postprocess(or_img, outputs)

        # 如果第一次检测有结果，直接返回
        if len(pred) > 0:
            return pred, or_img

        if args.no_45:
            return pred, or_img

        # 如果第一次检测没有结果，进行旋转后的第二次检测
        print("First detection found no results, trying with 45-degree rotation...")
        sys.stdout.flush()

        img_data_rot, or_img_rot, transform_info_rot = self.preprocess(img, mask_path, rotate=True)
        outputs_rot = self.onnx_session.run(None, {model_inputs[0].name: img_data_rot})
        pred_rot = self.postprocess(or_img_rot, outputs_rot)

        # 如果旋转后检测到结果，需要将坐标转换回未旋转的2048*2048图坐标系
        if len(pred_rot) > 0:
            # 将旋转结果转回未旋转的2048*2048图坐标系
            pred_canvas = self.transform_coordinates_back(pred_rot, transform_info_rot)
            return pred_canvas, or_img  # ✅ 坐标与 or_img 一致

        # 如果两次检测都没有结果，返回空列表
        return [], or_img


def draw(image, box_data):
    if len(box_data) > 0:
        np_data = np.array(box_data)
        boxes = np_data[..., :4].astype(np.int32)  # x1, y1, x2, y2
        scores = np_data[..., 4]
        classes = np_data[..., 5].astype(np.int32)
        for box, score, cl in zip(boxes, scores, classes):
            x1, y1, x2, y2 = box  # ✅ 正确的解包顺序
            cv2.rectangle(image, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(image, f"{CLASSES[cl]} {score:.2f}", (x1, max(0, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return image
    else:
        return None


def _infer_single_file(model, mask_path, file_info, debug):
    """Run inference on a single file, print one JSON-line result to stdout.

    file_info matches the inferenceBatch schema:
        {"preview": abs path, "filename": basename, "dir": abs dir, "id": uuid}
    Returns True on success, False if file is missing or non-image or threw.
    """
    file_path = file_info["preview"]
    filename = file_info["filename"]

    if not (os.path.isfile(file_path) and filename.lower().endswith((".png", ".bmp", ".jpg", ".jpeg"))):
        return False

    try:
        orientation = get_orientation(file_path)
        image = Image.open(file_path)
        image = adjust_image_orientation(image, orientation)
        image_array = np.array(image)
        if len(image_array.shape) == 3:
            image = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        else:
            image = image_array

        output, or_img = model.inference(image, mask_path, debug)
        outbox_convert = np.array(output).tolist()
        height, width = image.shape[:2]
        printInfo = {
            "outbox": outbox_convert,
            "width": width,
            "height": height,
            "file": file_path,
            "id": file_info["id"],
            "filename": filename,
            "dir": file_info["dir"],
        }
        print(json.dumps(printInfo), flush=True)
        sys.stdout.flush()

        if debug is True:
            or_img = draw(or_img, output)
            if or_img is not None:
                mmdebug_dir = os.path.join(file_info["dir"], "mmdebug")
                if not os.path.exists(mmdebug_dir):
                    os.makedirs(mmdebug_dir)
                output_image_path = os.path.join(mmdebug_dir, filename)
                cv2.imwrite(output_image_path, or_img)
        return True
    except Exception as e:
        err = {
            "type": "error",
            "file": file_path,
            "id": file_info.get("id"),
            "msg": "{}: {}".format(type(e).__name__, e),
        }
        print(json.dumps(err), flush=True)
        sys.stdout.flush()
        return False


def _build_file_info_from_path(file_path):
    """Build the inferenceBatch-shaped file_info dict from a path.
    Watcher code generates UUIDs here so engine doesn't have to.
    The "file" key in stdout carries the absolute path; "id" is a fresh UUID.
    """
    abs_path = os.path.abspath(file_path)
    return {
        "preview": abs_path,
        "filename": os.path.basename(abs_path),
        "dir": os.path.dirname(abs_path),
        "id": uuid.uuid4().hex,
    }


def inferenceBatch(mask_path, file_list, onnx_path, force_CPU, debug):
    model = YOLOv8(onnx_path, force_CPU)
    for file in file_list:
        _infer_single_file(model, mask_path, file, debug)


class ImageStreamHandler(FileSystemEventHandler):
    """watchdog event handler: enqueues newly-stabilized images.

    Half-written-file defense: camera/copy tools often create() a 0-byte file,
    then write() data, possibly with several modify() events. Reading on_created
    directly would see 0 bytes. We use an mtime stability window (default is 300 ms
    with no further modify to enter queue) and the main loop polls drain_ready()
    periodically to trigger inference.

    Same-name overwrite: on_modified also fires, but if path is already in
    _processed_recently we skip re-running inference.
    """

    # 平台一致性：Windows / macOS / Linux 上 watchdog 的 modify 事件频次差异很大，
    # 300 ms 是经验值，足以让 50 MB JPEG 写完；RAW/HEIC 移动设备连拍建议抬到 800 ms。
    DEFAULT_DEBOUNCE_MS = 300

    # "最近处理过" 的 TTL 缓存，避免 watchdog 在 backfill 时对同一文件
    # 重复触发 on_created / on_modified（NTFS / APFS 等会发出多 TTL 内多次事件）。
    DEFAULT_RECENTLY_TTL_SEC = 2.0

    def __init__(self, q, allowed_ext, debounce_ms=None, recently_ttl_sec=None):
        super().__init__()
        self.q = q
        self.allowed_ext = {e.lower() for e in allowed_ext}
        self.debounce_ms = debounce_ms if debounce_ms is not None else self.DEFAULT_DEBOUNCE_MS
        self.recently_ttl_sec = recently_ttl_sec if recently_ttl_sec is not None else self.DEFAULT_RECENTLY_TTL_SEC
        # path -> last_seen_mtime (float); entries older than self.debounce_ms without further
        # modify are drained into self.q by the main loop's drain_ready().
        self._pending = {}
        # path -> last_enqueued_mtime (float); lets us dedupe backfill+watch events.
        self._processed_recently = {}
        self._lock = threading.Lock()

    def _is_allowed(self, path):
        return os.path.splitext(path)[1].lower() in self.allowed_ext

    def _touch(self, path):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return False
        with self._lock:
            self._pending[path] = mtime
        return True

    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if not self._is_allowed(path):
            return
        self._touch(path)

    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if not self._is_allowed(path):
            return
        self._touch(path)

    def on_moved(self, event):
        if event.is_directory:
            return
        path = event.dest_path
        if not self._is_allowed(path):
            return
        self._touch(path)

    def drain_ready(self):
        """Move pending files that have been stable for >= debounce_ms into the queue.
        Returns a list of (path, mtime) tuples to be enqueued (caller wraps in file_info).
        """
        now = time.time()
        ready = []
        with self._lock:
            # Expired entries: mtime <= now - debounce_ms/1000
            cutoff = now - (self.debounce_ms / 1000.0)
            for path, mtime in list(self._pending.items()):
                if mtime <= cutoff:
                    ready.append((path, mtime))
                    del self._pending[path]
        return ready

    def mark_processed(self, path, mtime):
        """Record that this path has been enqueued so duplicate watchdog events
        within TTL window can be skipped.
        """
        with self._lock:
            self._processed_recently[path] = mtime
            # GC stale entries to avoid dict bloat
            now = time.time()
            expired = [p for p, t in self._processed_recently.items()
                       if now - t > self.recently_ttl_sec]
            for p in expired:
                del self._processed_recently[p]

    def is_recently_processed(self, path):
        """True if this path was enqueued within the TTL; watchdog events should be ignored."""
        now = time.time()
        with self._lock:
            expired = [p for p, t in self._processed_recently.items()
                       if now - t > self.recently_ttl_sec]
            for p in expired:
                del self._processed_recently[p]
            return path in self._processed_recently

    def enqueue_if_fresh(self, path, mtime):
        """For backfill: enqueue only if not already processed recently.
        Called by main loop after scan_existing + drain_ready for backfill items.
        Returns True if enqueued.
        """
        with self._lock:
            if path in self._processed_recently:
                return False
            self._processed_recently[path] = mtime
        self.q.put((path, mtime))
        return True


def scan_existing(folder, allowed_ext):
    """Enumerate files already in folder at startup. Bypasses debounce
    (these files existed before the watcher started, so watchdog won't fire on them)
    but still records them in _processed_recently to avoid double-processing
    if watchdog happens to emit a duplicate event later.
    Returns list of (path, mtime).
    """
    items = []
    try:
        names = sorted(os.listdir(folder))
    except OSError as e:
        print(json.dumps({"type": "error", "msg": "scan_existing failed: {}".format(e)}), flush=True)
        return items
    for name in names:
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in allowed_ext:
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        items.append((path, mtime))
    return items


def runWatchFolder(args):
    """Long-running watcher mode. Pre-existing files are processed as backfill
    at startup; new files appear via watchdog events.
    """
    if not _WATCHDOG_AVAILABLE:
        sys.stderr.write("watchdog is not installed. Install it: pip install watchdog\n")
        sys.exit(2)

    folder = os.path.abspath(args.watch_folder)
    if not os.path.isdir(folder):
        sys.stderr.write("watch_folder is not a directory: {}\n".format(folder))
        sys.exit(2)

    # watch_folder mode: only .jpg (per product requirement).
    # One-shot --img_directory mode keeps the broader .jpg/.jpeg/.png/.bmp set below
    # for backward compat with existing json_list inputs.
    allowed_ext = {".jpg"}
    mask_path = args.mask
    onnx_path = args.onnx_path
    force_CPU = args.force_CPU
    debug = args.debug
    processed_log_path = args.processed_log or ""
    exclude_log_path = args.exclude_log or ""

    print(json.dumps({"type": "starting", "folder": folder, "version": VERSION}), flush=True)

    # Initialize model once and keep in memory (watch_folder purpose: avoid
    # re-loading the ONNX session per file like --img_directory does).
    model = YOLOv8(onnx_path, force_CPU)

    q = queue.Queue()
    handler = ImageStreamHandler(q, allowed_ext)
    observer = Observer()
    observer.schedule(handler, folder, recursive=False)
    observer.start()

    # Persistent skip sets: file-based so they survive restarts. Both keyed by
    # basename (watch_folder is single-folder, basenames are unique within it).
    # The processed_log is also seeded by reading existing contents so that files
    # processed in a previous run are not re-processed on restart.
    exclude_set = _load_name_list_file(exclude_log_path, label="exclude_log") if exclude_log_path else set()
    processed_set = _load_name_list_file(processed_log_path, label="processed_log") if processed_log_path else set()

    # Ensure the processed_log file exists (touch) so external tail/cat consumers
    # see a stable file from the very first file processed. Only when configured.
    if processed_log_path:
        try:
            open(processed_log_path, "a", encoding="utf-8").close()
        except OSError as e:
            sys.stderr.write("processed_log: cannot touch {}: {}\n".format(processed_log_path, e))

    print(json.dumps({"type": "ready",
                      "folder": folder,
                      "version": VERSION,
                      "debounce_ms": handler.debounce_ms,
                      "exclude_log": len(exclude_set),
                      "processed_log_seed": len(processed_set),
                      }), flush=True)

    # Backfill pre-existing files at startup.
    existing = scan_existing(folder, allowed_ext)
    # Pre-filter against persistent skip sets (memory-set is empty before any
    # watchdog events have fired in this session, so we only need exclude_set
    # and processed_set here).
    filtered_existing = [
        (path, mtime) for (path, mtime) in existing
        if os.path.basename(path) not in exclude_set
        and os.path.basename(path) not in processed_set
    ]
    skipped_existing = len(existing) - len(filtered_existing)
    print(json.dumps({"type": "backfill_enqueued",
                      "count": len(filtered_existing),
                      "skipped_existing": skipped_existing}), flush=True)
    backfill_done = 0
    for path, mtime in filtered_existing:
        if handler.enqueue_if_fresh(path, mtime):
            backfill_done += 1
    print(json.dumps({"type": "backfill_complete", "count": backfill_done}), flush=True)

    # Main loop: poll for ready files (from watchdog events) AND from queue.
    # Two threads would be cleaner but a single polling loop keeps the contract simple.
    try:
        while True:
            # Drain pending watchdog events whose debounce has elapsed
            for path, mtime in handler.drain_ready():
                name = os.path.basename(path)
                if name in exclude_set:
                    continue  # user-marked exclude
                if name in processed_set:
                    # already processed in a previous run; drop silently
                    handler.mark_processed(path, mtime)
                    continue
                handler.enqueue_if_fresh(path, mtime)
            # Process queued files
            try:
                while True:
                    path, mtime = q.get_nowait()
                    name = os.path.basename(path)
                    if name in exclude_set:
                        handler.mark_processed(path, mtime)
                        continue
                    file_info = _build_file_info_from_path(path)
                    file_info["id"] = uuid.uuid4().hex  # override to fresh id
                    _infer_single_file(model, mask_path, file_info, debug)
                    handler.mark_processed(path, mtime)
                    # Persistent processed-log append: file I/O errors must NOT
                    # break the watcher, just log to stderr.
                    if processed_log_path:
                        try:
                            with open(processed_log_path, "a", encoding="utf-8") as f:
                                f.write(name + "\n")
                                f.flush()
                            processed_set.add(name)
                        except OSError as e:
                            sys.stderr.write("processed_log: write failed for {}: {}\n".format(name, e))
            except queue.Empty:
                pass
            # Sleep a small amount to avoid busy-waiting
            time.sleep(0.05)
    except KeyboardInterrupt:
        sys.stderr.write("interrupted, stopping watcher\n")
    finally:
        observer.stop()
        observer.join(timeout=2.0)
        print(json.dumps({"type": "stopped"}), flush=True)


def _load_name_list_file(path, label):
    """Load a one-name-per-line text file into a set. Empty lines and lines
    starting with '#' are ignored. Missing file is treated as empty set (not
    an error). Other I/O errors are reported to stderr and the set stays empty.

    Uses utf-8-sig so a UTF-8 BOM written by PowerShell `Out-File -Encoding utf8`
    (or Windows Notepad) is stripped; otherwise the first basename would be
    stored as "\ufeff1372-extract.jpg" and silently fail to match.
    """
    out = set()
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                name = line.strip()
                if not name or name.startswith("#"):
                    continue
                out.add(name)
    except FileNotFoundError:
        pass  # missing file == empty list, no warning
    except OSError as e:
        sys.stderr.write("{}: cannot read {}: {}\n".format(label, path, e))
    return out


def get_orientation(file_path):
    # 打开图像
    image = Image.open(file_path)

    # 获取 EXIF 数据
    exif_data = image._getexif()

    if exif_data is not None:
        for tag, value in exif_data.items():
            # 打印出每个标签和对应的值
            if TAGS.get(tag) == "Orientation":
                return value  # 返回 Orientation 信息
    return None  # 如果没有 Orientation 信息，则返回 None


def adjust_image_orientation(image, orientation):
    # 根据 Orientation 调整图像
    if orientation == 3:
        return image.rotate(180, expand=True)
    elif orientation == 6:
        return image.rotate(270, expand=True)
    elif orientation == 8:
        return image.rotate(90, expand=True)
    else:
        return image  # 不需旋转的情况


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    parser.add_argument("--licenses", action="store_true",
                        help="Print third-party license notices and exit")
    parser.add_argument("--mask", default="", help="Path to mask image (optional)")
    parser.add_argument("--img_directory", default="", help="Directory of images to process (one-shot mode)")
    parser.add_argument("--img_directory_list", metavar="FILE", help="JSON file with image paths (one-shot mode)")
    parser.add_argument("--watch_folder", default="",
                        help="Watch a folder for new images; mutually exclusive with --img_directory/--img_directory_list. Pre-existing files are processed as backfill at startup. Send SIGTERM/SIGKILL to stop.")
    parser.add_argument("--onnx_path", default="./V8L_1.0.onnx", help="ONNX model path")
    parser.add_argument("--force_CPU", action="store_true", default=False, help="Force CPU execution")
    parser.add_argument("--no_45", action="store_true", default=False, help="Disable 45-degree rotation fallback")
    parser.add_argument("--debug", action="store_true", default=False, help="Save annotated images to <dir>/mmdebug/<filename>")
    parser.add_argument("--processed_log", default="",
                        help="(watch_folder only) Append processed file basenames (one per line) to this file. Seeded from existing contents on startup so previously-processed files are skipped.")
    parser.add_argument("--exclude_log", default="",
                        help="(watch_folder only) One file basename per line; matching files are skipped without inference.")
    args = parser.parse_args()

    # --licenses / --version 早退出：不需要图片目录，也不需要加载模型。
    if args.licenses:
        print_third_party_notices()
        sys.exit(0)

    # Mutual exclusion: --watch_folder vs --img_directory / --img_directory_list
    one_shot_set = bool(args.img_directory or args.img_directory_list)
    if args.watch_folder and one_shot_set:
        parser.error("--watch_folder is mutually exclusive with --img_directory and --img_directory_list")
    if not args.watch_folder and not one_shot_set:
        parser.error("Either --img_directory / --img_directory_list or --watch_folder is required")

    if args.watch_folder:
        runWatchFolder(args)
        sys.exit(0)

    # --processed_log / --exclude_log only apply to watch_folder; warn (don't
    # error) so a copy-pasted CLI doesn't silently misbehave.
    if args.processed_log or args.exclude_log:
        sys.stderr.write(
            "note: --processed_log / --exclude_log are ignored in one-shot mode "
            "(only meaningful with --watch_folder)\n"
        )

    file_list = []
    allowed_extensions = [".jpg", ".jpeg", ".png", ".bmp"]
    if args.img_directory:
        for root, dirs, files in os.walk(args.img_directory):
            for index, file in enumerate(files):
                file_path = os.path.join(root, file)
                extension = os.path.splitext(file_path)[1].lower()
                if extension in allowed_extensions:
                    file_info = {"source": file_path, "preview": file_path, "id": index, "filename": file, "dir": os.path.abspath(root)}
                    file_list.append(file_info)

    if args.img_directory_list:
        file_path = args.img_directory_list
        if not file_path.endswith(".json"):
            parser.error("--img_directory_list must be a .json file")

        with open(file_path, "r", encoding="utf-8") as file:
            try:
                json_data = json.load(file)
                for path in json_data:
                    filename = os.path.basename(path["preview"])
                    directory = os.path.dirname(path["preview"])
                    path_data = {"filename": filename, "dir": directory}
                    path.update(path_data)
                file_list = json_data
            except json.JSONDecodeError as e:
                parser.error(file_path + " JSON parse error")

    inferenceBatch(args.mask, file_list, args.onnx_path, args.force_CPU, args.debug)
