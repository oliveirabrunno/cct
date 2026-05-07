from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from utils.logger import get_logger

log = get_logger(__name__)


class ImageProcessor:

    BRAND_DARK = (10, 10, 10)
    BRAND_ACCENT = (200, 241, 53)
    BRAND_WHITE = (255, 255, 255)

    def prepare_for_card(
        self,
        image_path: str,
        target_size: tuple = (400, 500),
        style: str = "clean",
    ) -> Image.Image:
        img = Image.open(image_path).convert("RGB")
        img = self._smart_crop(img, target_size)

        if style == "duotone":
            img = self._apply_duotone(img)
        elif style == "silhouette":
            img = self._apply_silhouette(img)
        else:
            img = self._apply_clean(img)

        return img

    def _smart_crop(self, img: Image.Image, target: tuple) -> Image.Image:
        w, h = img.size
        target_w, target_h = target
        target_ratio = target_w / target_h
        current_ratio = w / h

        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top_bias = int(new_h * 0.15)
            img = img.crop((0, top_bias, w, top_bias + new_h))

        return img.resize(target, Image.LANCZOS)

    def _apply_duotone(self, img: Image.Image) -> Image.Image:
        gray = img.convert("L")
        duotone = Image.new("RGB", img.size)

        dark = self.BRAND_DARK
        light = self.BRAND_ACCENT
        pixels = gray.load()
        result = duotone.load()

        for y in range(img.height):
            for x in range(img.width):
                t = pixels[x, y] / 255.0
                r = int(dark[0] + (light[0] - dark[0]) * t)
                g = int(dark[1] + (light[1] - dark[1]) * t)
                b = int(dark[2] + (light[2] - dark[2]) * t)
                result[x, y] = (r, g, b)

        return duotone

    def _apply_silhouette(self, img: Image.Image) -> Image.Image:
        gray = img.convert("L")
        result = Image.new("RGB", img.size)
        pixels = gray.load()
        res_pixels = result.load()

        for y in range(img.height):
            for x in range(img.width):
                if pixels[x, y] < 128:
                    res_pixels[x, y] = self.BRAND_DARK
                else:
                    res_pixels[x, y] = self.BRAND_ACCENT

        return result

    def _apply_clean(self, img: Image.Image) -> Image.Image:
        img = ImageEnhance.Contrast(img).enhance(1.1)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
        return img

    def create_h2h_composition(
        self,
        img_a: Image.Image,
        img_b: Image.Image,
        width: int = 1080,
        height: int = 1080,
    ) -> Image.Image:
        canvas = Image.new("RGB", (width, height), self.BRAND_DARK)
        half_w = width // 2

        img_a_resized = img_a.resize((half_w, height), Image.LANCZOS)
        img_b_resized = img_b.resize((half_w, height), Image.LANCZOS)
        img_b_flipped = img_b_resized.transpose(Image.FLIP_LEFT_RIGHT)

        canvas.paste(img_a_resized, (0, 0))
        canvas.paste(img_b_flipped, (half_w, 0))

        draw = ImageDraw.Draw(canvas)
        draw.line([(half_w - 2, 0), (half_w + 2, height)],
                  fill=self.BRAND_ACCENT, width=4)

        return canvas

    def apply_gradient_overlay(
        self,
        img: Image.Image,
        direction: str = "bottom",
    ) -> Image.Image:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        w, h = img.size

        if direction == "bottom":
            for y in range(h // 2, h):
                alpha = int(200 * (y - h // 2) / (h // 2))
                draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
        elif direction == "top":
            for y in range(0, h // 2):
                alpha = int(200 * (h // 2 - y) / (h // 2))
                draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

        result = Image.alpha_composite(img.convert("RGBA"), overlay)
        return result.convert("RGB")
