from typing import Dict, Optional, Union, Tuple, Callable, Any

import numpy as np
from PIL import Image

from .lime import (
    create_segments,
    generate_samples,
    generate_images,
    predict_images,
    weigh_segments,
)
from .visualize import select_segments, generate_overlay


def explain_classification(
    image: np.ndarray,
    predict_fn: Callable[[np.ndarray], np.ndarray],
    label_idx: Optional[int] = None,
    segmentation_method: str = "slic",
    segmentation_settings: Optional[Dict[str, Any]] = None,
    num_of_samples: int = 64,
    p: float = 0.33,
) -> Tuple[np.ndarray, np.ndarray]:
    """

    For more detailed control, we recommend you create your own function, using this
    function as a template.

    Parameters
    ----------
    image : np.ndarray
        The image to explain as a three-dimensional array of shape
        (image_width, image_height, 3) representing an RGB image.

    predict_fn : Callable
        A function that takes an input of shape (num_of_samples, image_width, image_height, 3)
        and returns an array of shape (num_of_samples, num_of_classes).

    label_idx : int, optional
        The index of the label to explain in the output of `predict_fn()`.
        If not given, this corresponds to the class that `predict_fn()` assigns
        to the image.

    segmentation_method : str, default "slic"
        The method used to segment the image into superpixels.
        See `lime.create_segments()` for available methods.

    segmentation_settings : dict, optional
        The parameters to be passed to the segmentation method.
        See `lime.create_segments()` for details.

    num_of_samples : int, default 64
        The number of sample images to generate for calculating the explanation.

    p : float, default 0.33
        The probability of a segment to be replaced in a sample.

    Returns
    -------
    The segment_mask, a two-dimensional array of shape (image_width, image_height).

    The segment_weights, a one-dimensional array whose length is equal to
    the number of segments.

    Example
    -------

    # TODO: Add end-to-end example

    """
    if label_idx is None:
        label_idx = int(np.argmax(predict_fn(image[None, :, :, :])))

    segment_mask = create_segments(
        image=image,
        segmentation_method=segmentation_method,
        segmentation_settings=segmentation_settings,
    )

    samples = generate_samples(
        segment_mask=segment_mask, num_of_samples=num_of_samples, p=p
    )

    images = generate_images(image=image, segment_mask=segment_mask, samples=samples)

    predictions = predict_images(images=images, predict_fn=predict_fn)

    segment_weights = weigh_segments(
        samples=samples, predictions=predictions, label_idx=label_idx
    )

    return segment_mask, segment_weights


def render_explanation(
    image: np.ndarray,
    segment_mask: np.ndarray,
    segment_weights: np.ndarray,
    positive: Optional[Union[Tuple[int], str]] = "green",
    negative: Optional[Union[Tuple[int], str]] = None,
    opacity: float = 0.7,
    coverage: float = 0.2,
) -> Image:
    """Takes the segment_mask and segment_weights produced by `explain_classification()` and
    renders a visual explanation.

    Parameters
    ----------
    image : np.ndarray
        The image to explain the classification for as a three-dimensional array
        of shape (image_width, image_height, 3) representing an RGB image.

    segment_mask : np.ndarray
        The mask generated by `lime.create_segments()`: An array of shape (image_width, image_height).

    segment_weights : np.ndarray
        The weights produced by `lime.weigh_segments()`: A one-dimensional array of length num_of_segments.

    positive : str or int 3-tuple (RGB), optional, default "green"
        The color for the segments that contribute positively towards the classification.
        If `None`, these segments are not colored.

    negative : str or int 3-tuple (RGB), optional
        The color for the segments that contribute negatively towards the classification.
        If `None` (the default), these segments are not colored.

    opacity : float, default 0.7
        The opacity of the explanation overlay.

    coverage : float, default 0.2
        The coverage of each overlay relative to the area of the image.
        E.g., if set to 0.2 (the default), about 20% of the image are colored.

    Returns
    -------
    The rendered explanation as a PIL Image object.

    # TODO: Describe how to work with it

    Example
    -------

    # TODO: Add end-to-end example

    """
    final_img = Image.fromarray(image.astype(np.int8), "RGB").convert("RGBA")

    if positive is not None:
        positive_segments = select_segments(
            segment_weights, segment_mask, coverage=coverage
        )
        positive_overlay = generate_overlay(
            segment_mask, positive_segments, color=positive, opacity=opacity
        )
        overlay_image = Image.fromarray(positive_overlay.astype(np.int8), "RGBA")
        final_img.alpha_composite(overlay_image)

    if negative is not None:
        negative_segments = select_segments(
            -segment_weights, segment_mask, coverage=coverage
        )
        negative_overlay = generate_overlay(
            segment_mask, negative_segments, color=negative, opacity=opacity
        )
        overlay_image = Image.fromarray(negative_overlay.astype(np.int8), "RGBA")
        final_img.alpha_composite(overlay_image)

    return final_img