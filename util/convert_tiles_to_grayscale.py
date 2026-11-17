import os
import time

from PIL import Image


class ImageConversion:
    def __init__(self, src, dest):
        self._src = src
        self._dest = dest

    def convert(self, mode: str) -> None:
        with Image.open(self._src) as img:
            grayscale_img = img.convert(mode)
            grayscale_img.save(self._dest)

    def __repr__(self):
        return f"ImageConversion(src='{self._src}', dst='{self._dest}'"

    @staticmethod
    def create_conversions_list_from_folder_paths(src_folder, dest_folder):
        conversions = []

        for root, dirs, files in os.walk(src_folder):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                    src_file_path = os.path.join(root, file)
                    dest_file_path = os.path.join(root.replace(src_folder, dest_folder, 1), file)

                    conversions.append(ImageConversion(src_file_path, dest_file_path))
        return conversions


def create_folder_structure(src, dest):
    for root, dirs, files in os.walk(src):
        dest_path = root.replace(src, dest, 1)

        if not os.path.exists(dest_path):
            os.makedirs(dest_path)


def main():
    source_dir = '../static/tiles/osm'
    destination_dir = '../static/tiles/osm_grayscale'

    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    create_folder_structure(source_dir, destination_dir)
    image_conversions = ImageConversion.create_conversions_list_from_folder_paths(source_dir, destination_dir)
    number_of_image_conversions = len(image_conversions)

    for image_conversion, n in zip(image_conversions, range(number_of_image_conversions)):
        start_time = time.time()
        image_conversion.convert('L')
        print(f"Progress: {n:8}/{number_of_image_conversions} = {100 * n / number_of_image_conversions:.2f}% "
              f"Conversion: {image_conversion} in {(time.time()-start_time)*1000:.2f}ms")

    print("All images have been converted to grayscale and saved in the corresponding folder structure.")


if __name__ == "__main__":
    main()
