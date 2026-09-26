"""FlattenAlphaImagesPipeline: transparent source images must come out on
white, not black.

Driven through get_images() rather than convert_image() on purpose: the
stock bug only shows up there, because get_images() passes convert_image()
an exif_transpose() copy whose ``format`` is None.
"""

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from scrapy.http import Request, Response
from scrapy.utils.test import get_crawler

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scraper"))

from lidaldi.pipelines import (  # noqa: E402
    ITEM_PIPELINES,
    FlattenAlphaImagesPipeline,
)

URL = "https://www.lidl.ie/assets/gcp0123456789abcdef.png"
WHITE = (255, 255, 255)
RED = (200, 30, 30)


@pytest.fixture
def pipeline(tmp_path):
    crawler = get_crawler(settings_dict={"IMAGES_STORE": str(tmp_path)})
    return FlattenAlphaImagesPipeline.from_crawler(crawler)


def _png(image):
    buf = BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def _run(pipeline, body):
    request = Request(URL)
    response = Response(URL, body=body, request=request)
    (path, image, buf), = pipeline.get_images(response, request, None)
    return path, image, Image.open(BytesIO(buf.getvalue()))


def _transparent_with_red_centre(mode):
    """40x40 fully transparent canvas (RGB of 0 underneath) with an opaque
    red square in the middle, converted to ``mode``."""
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (20, 20), RED + (255,)), (10, 10))
    return im if mode == "RGBA" else im.convert(mode)


def _close(pixel, expected, tol=8):
    return all(abs(a - b) <= tol for a, b in zip(pixel, expected))


@pytest.mark.parametrize("mode", ["RGBA", "LA", "P"])
def test_transparent_background_is_flattened_to_white(pipeline, mode):
    _, image, saved = _run(pipeline, _png(_transparent_with_red_centre(mode)))

    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == WHITE
    assert saved.format == "JPEG"
    assert _close(saved.getpixel((0, 0)), WHITE)
    if mode != "LA":  # LA is greyscale; only the background matters there
        assert _close(image.getpixel((20, 20)), RED)


def test_rgb_colour_key_transparency_is_flattened_to_white(pipeline):
    # RGB PNG with a tRNS colour key: black means transparent.
    im = Image.new("RGB", (40, 40), (0, 0, 0))
    im.paste(Image.new("RGB", (20, 20), RED), (10, 10))
    buf = BytesIO()
    im.save(buf, "PNG", transparency=(0, 0, 0))

    _, image, _ = _run(pipeline, buf.getvalue())

    assert image.getpixel((0, 0)) == WHITE
    assert _close(image.getpixel((20, 20)), RED)


def test_opaque_image_is_left_alone(pipeline):
    im = Image.new("RGB", (40, 40), (0, 0, 0))  # genuinely black photo
    _, image, _ = _run(pipeline, _png(im))
    assert image.getpixel((0, 0)) == (0, 0, 0)


def test_paths_are_versioned_so_stale_black_images_are_not_reused(pipeline):
    path, _, _ = _run(pipeline, _png(Image.new("RGB", (40, 40))))
    assert path.startswith("full/v2/")
    assert path.endswith(".jpg")
    assert "/full/" not in path


@pytest.mark.parametrize("spider_module,cls_name", [
    ("lidaldi.spiders.aldi_spider", "AldiSpider"),
    ("lidaldi.spiders.lidl_spider", "LidlSpider"),
])
def test_spiders_wire_the_fixed_pipeline(spider_module, cls_name):
    # The live settings.py is never synced by the installer, so the spiders
    # themselves must carry the pipeline wiring -- including the error
    # checker, since custom_settings replaces ITEM_PIPELINES wholesale.
    module = __import__(spider_module, fromlist=[cls_name])
    pipelines = getattr(module, cls_name).custom_settings["ITEM_PIPELINES"]
    assert pipelines is ITEM_PIPELINES
    assert "lidaldi.pipelines.FlattenAlphaImagesPipeline" in pipelines
    assert "lidaldi.pipelines.ErrorCheckingPipeline" in pipelines
    assert "scrapy.pipelines.images.ImagesPipeline" not in pipelines
