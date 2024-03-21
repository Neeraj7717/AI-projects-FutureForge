import io
import os
import cv2
from PIL import Image


class cv2_operations:
    @staticmethod
    def draw_bounding_boxes(image_path, bounding_boxes, classes, output_path):
        image = cv2.imread(image_path)

        for i in range(len(classes)):
            x, y, w, h = bounding_boxes[i]
            color = (0, 255, 0)  # Green color for the bounding boxes
            thickness = 2
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            cv2.rectangle(image, (int(x), int(y)), (int(w), int(h)), color, thickness)

            label_text = classes[i]
            cv2.putText(
                image,
                label_text,
                (int(x), int(y) - 5),
                font,
                font_scale,
                color,
                thickness,
            )

        cv2.imwrite(output_path, image)

    @staticmethod
    def crop_and_save_image(image_path, bbox, save_path):
        img = cv2.imread(image_path)
        xmin, ymin, xmax, ymax = bbox
        cropped_img = img[int(ymin) : int(ymax), int(xmin) : int(xmax)]
        output_dir = os.path.dirname(save_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Save the cropped image
        cv2.imwrite(save_path, cropped_img)

    @staticmethod
    def image_to_bytes(image_array):
        # Convert the image array to a PIL Image
        image = Image.fromarray(image_array)
        # Create an in-memory binary stream (bytes buffer)
        image_bytes = io.BytesIO()
        # Save the PIL Image to the bytes buffer in JPEG format
        image.save(image_bytes, format="JPEG")
        # Seek to the beginning of the stream (position 0)
        image_bytes.seek(0)
        return image_bytes
