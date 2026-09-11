"""
aadhaarconversion.py

============================================================

Aadhaar QR Code Conversion Module.

INPUT

-----

    nationalid/aadhaar.jpeg

    or

    nationalid/aadhar.jpeg

    or

    nationalid/aadhar.jpg

OUTPUT

------

    nationalid/aadhaar.json

The module attempts to decode the Aadhaar QR code using

multiple image preprocessing techniques and QR decoders.

"""

import json

import logging

import re

from pathlib import Path

from typing import Any, Dict, Optional





import cv2

from pyzbar.pyzbar import decode as pyzbar_decode

try:

    import zxingcpp

except ImportError:

    zxingcpp = None





# ============================================================

# PATH CONFIGURATION

# ============================================================

BASE_DIR = Path(__file__).resolve().parent

OUTPUT_FILE = BASE_DIR / "aadhaar.json"

IMAGE_FILES = [

    BASE_DIR / "aadhaar.jpeg",

    BASE_DIR / "aadhaar.jpg",

    BASE_DIR / "aadhar.jpeg",

    BASE_DIR / "aadhar.jpg",

    BASE_DIR / "aadhaar.png",

    BASE_DIR / "aadhar.png",

]





# ============================================================

# LOGGING CONFIGURATION

# ============================================================

logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s | %(levelname)s | %(message)s",

)

logger = logging.getLogger(

    "aadhaar_conversion"

)





# ============================================================

# FIND AADHAAR IMAGE

# ============================================================

def find_aadhaar_image(

    image_path: Optional[Path] = None

) -> Path:

    if image_path is not None:

        path = Path(image_path)

        if path.exists():

            return path

        raise FileNotFoundError(

            f"Aadhaar image not found: {path}"

        )

    for path in IMAGE_FILES:

        if path.exists():

            return path

    raise FileNotFoundError(

        "Aadhaar image not found. Expected one of: "

        + ", ".join(

            str(path.name)

            for path in IMAGE_FILES

        )

    )





# ============================================================

# LOAD IMAGE

# ============================================================

def load_image(

    image_path: Path

):

    image = cv2.imread(

        str(image_path),

        cv2.IMREAD_COLOR

    )

    if image is None:

        raise ValueError(

            f"Could not read Aadhaar image: {image_path}"

        )

    if image.size == 0:

        raise ValueError(

            f"Aadhaar image is empty: {image_path}"

        )

    logger.info(

        "Aadhaar image loaded: %s",

        image_path

    )

    logger.info(

        "Image size: %sx%s",

        image.shape[1],

        image.shape[0]

    )

    return image





# ============================================================

# ADD QR QUIET ZONE

# ============================================================

def add_quiet_zone(

    image,

    border_size=80

):

    if len(image.shape) == 3:

        value = (255, 255, 255)

    else:

        value = 255

    return cv2.copyMakeBorder(

        image,

        border_size,

        border_size,

        border_size,

        border_size,

        cv2.BORDER_CONSTANT,

        value=value

    )





# ============================================================

# IMAGE PREPROCESSING

# ============================================================

def create_preprocessed_images(

    image

):

    processed_images = []

    gray = cv2.cvtColor(

        image,

        cv2.COLOR_BGR2GRAY

    )





    # --------------------------------------------------------

    # Original grayscale image

    # --------------------------------------------------------

    processed_images.append(

        add_quiet_zone(

            gray,

            40

        )

    )





    # --------------------------------------------------------

    # Slightly cropped versions

    # --------------------------------------------------------

    height, width = gray.shape[:2]





    crop_percentages = (

        0.00,

        0.01,

        0.02,

        0.03,

        0.04,

    )





    for percentage in crop_percentages:

        crop_x = int(width * percentage)

        crop_y = int(height * percentage)





        if (

            width - (2 * crop_x) <= 0

            or height - (2 * crop_y) <= 0

        ):

            continue





        cropped = gray[

            crop_y:height - crop_y,

            crop_x:width - crop_x

        ]





        # ----------------------------------------------------

        # Upscaling

        # ----------------------------------------------------

        for scale in (

            2,

            3,

            4,

            6,

            8,

        ):

            upscaled = cv2.resize(

                cropped,

                None,

                fx=scale,

                fy=scale,

                interpolation=cv2.INTER_CUBIC

            )





            processed_images.append(

                add_quiet_zone(

                    upscaled

                )

            )





            # ------------------------------------------------

            # Lanczos upscaling

            # ------------------------------------------------

            lanczos = cv2.resize(

                cropped,

                None,

                fx=scale,

                fy=scale,

                interpolation=cv2.INTER_LANCZOS4

            )





            processed_images.append(

                add_quiet_zone(

                    lanczos

                )

            )





            # ------------------------------------------------

            # Median denoising

            # ------------------------------------------------

            median = cv2.medianBlur(

                upscaled,

                3

            )





            processed_images.append(

                add_quiet_zone(

                    median

                )

            )





            # ------------------------------------------------

            # Gaussian blur + sharpening

            # ------------------------------------------------

            blurred = cv2.GaussianBlur(

                upscaled,

                (0, 0),

                1.0

            )





            sharpened = cv2.addWeighted(

                upscaled,

                2.0,

                blurred,

                -1.0,

                0

            )





            processed_images.append(

                add_quiet_zone(

                    sharpened

                )

            )





            # ------------------------------------------------

            # Otsu threshold

            # ------------------------------------------------

            _, otsu = cv2.threshold(

                upscaled,

                0,

                255,

                cv2.THRESH_BINARY

                + cv2.THRESH_OTSU

            )





            processed_images.append(

                add_quiet_zone(

                    otsu

                )

            )





            # ------------------------------------------------

            # Inverted Otsu

            # ------------------------------------------------

            _, otsu_inverse = cv2.threshold(

                upscaled,

                0,

                255,

                cv2.THRESH_BINARY_INV

                + cv2.THRESH_OTSU

            )





            processed_images.append(

                add_quiet_zone(

                    otsu_inverse

                )

            )





            # ------------------------------------------------

            # Adaptive threshold

            # ------------------------------------------------

            adaptive = cv2.adaptiveThreshold(

                upscaled,

                255,

                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,

                cv2.THRESH_BINARY,

                31,

                5

            )





            processed_images.append(

                add_quiet_zone(

                    adaptive

                )

            )





            # ------------------------------------------------

            # Adaptive threshold with larger block

            # ------------------------------------------------

            adaptive_large = cv2.adaptiveThreshold(

                upscaled,

                255,

                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,

                cv2.THRESH_BINARY,

                51,

                7

            )





            processed_images.append(

                add_quiet_zone(

                    adaptive_large

                )

            )





            # ------------------------------------------------

            # CLAHE contrast enhancement

            # ------------------------------------------------

            clahe = cv2.createCLAHE(

                clipLimit=3.0,

                tileGridSize=(8, 8)

            )





            enhanced = clahe.apply(

                upscaled

            )





            processed_images.append(

                add_quiet_zone(

                    enhanced

                )

            )



    logger.info(

        "Generated %s preprocessing variants.",

        len(processed_images)

    )





    return processed_images





# ============================================================

# ROTATE IMAGE

# ============================================================

def create_rotated_images(

    image

):

    rotated_images = [

        image

    ]





    height, width = image.shape[:2]

    center = (

        width // 2,

        height // 2

    )





    for angle in (

        -2,

        -1,

        1,

        2,

    ):

        matrix = cv2.getRotationMatrix2D(

            center,

            angle,

            1.0

        )





        rotated = cv2.warpAffine(

            image,

            matrix,

            (

                width,

                height

            ),

            flags=cv2.INTER_CUBIC,

            borderMode=cv2.BORDER_CONSTANT,

            borderValue=255

        )





        rotated_images.append(

            rotated

        )





    return rotated_images





# ============================================================

# OPENCV QR DECODER

# ============================================================

def decode_with_opencv(

    image

) -> Optional[str]:

    detector = cv2.QRCodeDetector()





    try:

        data, points, _ = detector.detectAndDecode(

            image

        )





        if data:

            return data

    except Exception as exc:

        logger.debug(

            "OpenCV QR decoding failed: %s",

            exc

        )





    return None





# ============================================================

# OPENCV CURVED QR DECODER

# ============================================================

def decode_curved_with_opencv(

    image

) -> Optional[str]:

    detector = cv2.QRCodeDetector()





    try:

        if hasattr(

            detector,

            "detectAndDecodeCurved"

        ):

            data, points, _ = detector.detectAndDecodeCurved(

                image

            )





            if data:

                return data

    except Exception as exc:

        logger.debug(

            "OpenCV curved QR decoding failed: %s",

            exc

        )





    return None





# ============================================================

# OPENCV MULTI QR DECODER

# ============================================================

def decode_multi_with_opencv(

    image

) -> Optional[str]:

    detector = cv2.QRCodeDetector()





    try:

        result = detector.detectAndDecodeMulti(

            image

        )





        if len(result) == 4:

            success, decoded_info, _, _ = result





            if success and decoded_info:

                for data in decoded_info:

                    if data:

                        return data

    except Exception as exc:

        logger.debug(

            "OpenCV multi QR decoding failed: %s",

            exc

        )





    return None





# ============================================================

# PYZBAR QR DECODER

# ============================================================

def decode_with_pyzbar(

    image

) -> Optional[str]:

    try:

        decoded_objects = pyzbar_decode(

            image

        )





        for obj in decoded_objects:

            data = obj.data





            if isinstance(

                data,

                bytes

            ):

                data = data.decode(

                    "utf-8",

                    errors="replace"

                )





            if data:

                return data





    except Exception as exc:

        logger.debug(

            "pyzbar QR decoding failed: %s",

            exc

        )





    return None





# ============================================================

# ZXING QR DECODER

# ============================================================

def decode_with_zxing(

    image

) -> Optional[str]:

    if zxingcpp is None:

        return None





    try:

        results = zxingcpp.read_barcodes(

            image

        )





        for result in results:

            if result.text:

                return result.text





    except Exception as exc:

        logger.debug(

            "ZXing QR decoding failed: %s",

            exc

        )





    return None





# ============================================================

# QR DECODING PIPELINE

# ============================================================

def decode_aadhaar_qr(

    image

) -> Optional[str]:

    processed_images = create_preprocessed_images(

        image

    )





    total_images = len(

        processed_images

    )





    if zxingcpp is not None:

        logger.info(

            "ZXing-C++ QR decoder is available."

        )

    else:

        logger.warning(

            "ZXing-C++ is not installed. "

            "OpenCV and pyzbar will be used."

        )





    for index, processed in enumerate(

        processed_images,

        start=1

    ):

        logger.info(

            "Trying QR decoder on preprocessing variant %s/%s",

            index,

            total_images

        )





        # ----------------------------------------------------

        # Rotation attempts

        # ----------------------------------------------------

        rotated_images = create_rotated_images(

            processed

        )





        for rotation_index, rotated in enumerate(

            rotated_images,

            start=1

        ):

            if rotation_index > 1:

                logger.debug(

                    "Trying rotation variant %s.",

                    rotation_index

                )





            # ------------------------------------------------

            # ZXing-C++

            # ------------------------------------------------

            data = decode_with_zxing(

                rotated

            )





            if data:

                logger.info(

                    "QR successfully decoded using ZXing-C++."

                )

                return data





            # ------------------------------------------------

            # OpenCV normal decoder

            # ------------------------------------------------

            data = decode_with_opencv(

                rotated

            )





            if data:

                logger.info(

                    "QR successfully decoded using OpenCV."

                )

                return data





            # ------------------------------------------------

            # OpenCV curved decoder

            # ------------------------------------------------

            data = decode_curved_with_opencv(

                rotated

            )





            if data:

                logger.info(

                    "QR successfully decoded using OpenCV curved decoder."

                )

                return data





            # ------------------------------------------------

            # OpenCV multi decoder

            # ------------------------------------------------

            data = decode_multi_with_opencv(

                rotated

            )





            if data:

                logger.info(

                    "QR successfully decoded using OpenCV multi decoder."

                )

                return data





            # ------------------------------------------------

            # pyzbar

            # ------------------------------------------------

            data = decode_with_pyzbar(

                rotated

            )





            if data:

                logger.info(

                    "QR successfully decoded using pyzbar."

                )

                return data





    logger.warning(

        "QR code could not be decoded from the image."

    )





    return None





# ============================================================

# EXTRACT AADHAAR NUMBER

# ============================================================

def extract_aadhaar_number(

    text: str

) -> Optional[str]:

    if not text:

        return None





    patterns = [

        r"\b\d{4}\s\d{4}\s\d{4}\b",

        r"\b\d{12}\b",

    ]





    for pattern in patterns:

        match = re.search(

            pattern,

            text

        )





        if match:

            value = match.group(

                0

            )





            return value.replace(

                " ",

                ""

            )





    return None





# ============================================================

# EXTRACT DATE OF BIRTH

# ============================================================

def extract_date_of_birth(

    text: str

) -> Optional[str]:

    if not text:

        return None





    patterns = [

        r"\b\d{2}/\d{2}/\d{4}\b",

        r"\b\d{2}-\d{2}-\d{4}\b",

        r"\b\d{4}-\d{2}-\d{2}\b",

    ]





    for pattern in patterns:

        match = re.search(

            pattern,

            text

        )





        if match:

            return match.group(

                0

            )





    return None





# ============================================================

# PARSE QR DATA

# ============================================================

def parse_qr_data(

    qr_data: Optional[str]

) -> Dict[str, Any]:

    result = {

        "aadhaar_number":

            None,

        "name":

            None,

        "name_native":

            None,

        "date_of_birth":

            None,

        "gender":

            None,

        "address":

            None,

        "pincode":

            None,

        "qr_data":

            qr_data,

    }





    if not qr_data:

        return result





    # --------------------------------------------------------

    # JSON QR payload

    # --------------------------------------------------------

    try:

        parsed = json.loads(

            qr_data

        )





        if isinstance(

            parsed,

            dict

        ):

            for key in result:

                if key == "qr_data":

                    continue





                if key in parsed:

                    result[key] = parsed[key]





            return result





    except Exception:

        pass





    # --------------------------------------------------------

    # XML QR payload

    # --------------------------------------------------------

    if qr_data.startswith(

        "<"

    ):

        aadhaar_number = re.search(

            r'(?:uid|aadhaar|aadhaar_number|uidNumber)="?(\d{12})',

            qr_data,

            re.IGNORECASE

        )





        name = re.search(

            r'name="([^"]+)"',

            qr_data,

            re.IGNORECASE

        )





        gender = re.search(

            r'(?:gender|gnd)="([^"]+)"',

            qr_data,

            re.IGNORECASE

        )





        dob = re.search(

            r'(?:dob|date_of_birth)="([^"]+)"',

            qr_data,

            re.IGNORECASE

        )





        pincode = re.search(

            r'(?:pc|pincode)="?(\d{6})',

            qr_data,

            re.IGNORECASE

        )





        if aadhaar_number:

            result[

                "aadhaar_number"

            ] = aadhaar_number.group(

                1

            )





        if name:

            result[

                "name"

            ] = name.group(

                1

            )





        if gender:

            result[

                "gender"

            ] = gender.group(

                1

            )





        if dob:

            result[

                "date_of_birth"

            ] = dob.group(

                1

            )





        if pincode:

            result[

                "pincode"

            ] = pincode.group(

                1

            )





        return result





    # --------------------------------------------------------

    # Plain text QR payload

    # --------------------------------------------------------

    result[

        "aadhaar_number"

    ] = extract_aadhaar_number(

        qr_data

    )





    result[

        "date_of_birth"

    ] = extract_date_of_birth(

        qr_data

    )





    # --------------------------------------------------------

    # Common Aadhaar QR key/value formats

    # --------------------------------------------------------

    field_patterns = {

        "name": [

            r"(?:name|NAME)[:=]\s*([^|;\n]+)",

        ],

        "gender": [

            r"(?:gender|sex|GENDER)[:=]\s*([MFOTmfot]+)",

        ],

        "pincode": [

            r"(?:pincode|pin|PIN)[:=]\s*(\d{6})",

        ],

        "address": [

            r"(?:address|ADDRESS)[:=]\s*([^|;\n]+)",

        ],

    }





    for field, patterns in field_patterns.items():

        for pattern in patterns:

            match = re.search(

                pattern,

                qr_data

            )





            if match:

                result[field] = (

                    match.group(1)

                    .strip()

                )





                break





    return result





# ============================================================

# BUILD JSON OUTPUT

# ============================================================

def build_output(

    image_path: Path,

    qr_data: Optional[str]

) -> Dict[str, Any]:

    image = cv2.imread(

        str(image_path)

    )





    if image is None:

        raise ValueError(

            f"Could not read image: {image_path}"

        )





    height, width = image.shape[:2]





    format_name = image_path.suffix.replace(

        ".",

        ""

    ).upper()





    aadhaar_data = parse_qr_data(

        qr_data

    )





    aadhaar_data["image"] = {

        "filename":

            image_path.name,

        "width":

            width,

        "height":

            height,

        "format":

            format_name,

    }





    return {

        "document_type":

            "aadhaar",

        "aadhaar":

            aadhaar_data,

    }





# ============================================================

# SAVE JSON

# ============================================================

def save_json(

    data: Dict[str, Any]

) -> None:

    try:

        with OUTPUT_FILE.open(

            "w",

            encoding="utf-8"

        ) as file:

            json.dump(

                data,

                file,

                indent=4,

                ensure_ascii=False

            )





    except OSError as exc:

        raise RuntimeError(

            f"Could not write Aadhaar JSON: {exc}"

        )





    logger.info(

        "Aadhaar JSON successfully saved: %s",

        OUTPUT_FILE

    )





# ============================================================

# MAIN AADHAAR PROCESSOR

# ============================================================

def process_aadhaar_image(

    image_path: Optional[Path] = None

) -> Dict[str, Any]:

    logger.info(

        "Starting Aadhaar QR conversion."

    )





    try:

        image_file = find_aadhaar_image(

            image_path

        )





        image = load_image(

            image_file

        )





        qr_data = decode_aadhaar_qr(

            image

        )





        result = build_output(

            image_file,

            qr_data

        )





        save_json(

            result

        )





        if qr_data:

            logger.info(

                "Aadhaar QR conversion completed successfully."

            )

        else:

            logger.warning(

                "Aadhaar image processed, but QR data was not decoded."

            )





        return result





    except Exception as exc:

        logger.exception(

            "Aadhaar conversion failed."

        )





        result = {

            "document_type":

                "aadhaar",

            "aadhaar": {

                "aadhaar_number":

                    None,

                "name":

                    None,

                "name_native":

                    None,

                "date_of_birth":

                    None,

                "gender":

                    None,

                "address":

                    None,

                "pincode":

                    None,

                "qr_data":

                    None,

                "image":

                    None,

            },

            "error":

                str(exc),

        }





        save_json(

            result

        )





        return result





# ============================================================

# PROGRAM ENTRY POINT

# ============================================================

if __name__ == "__main__":

    process_aadhaar_image()