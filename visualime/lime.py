from typing import Dict, Callable, Any, Optional, Union

import numpy as np
from skimage.color import rgb2gray
from skimage.filters import sobel
from skimage.segmentation import felzenszwalb, slic, quickshift, watershed
from sklearn.linear_model import BayesianRidge, Lasso, LinearRegression


def _watershed(image: np.ndarray, **kwargs):
    gradient = sobel(rgb2gray(image))
    return watershed(image=gradient, **kwargs)


SEGMENTATION_METHODS = {
    "felzenszwalb": (felzenszwalb, {"scale": 250, "sigma": 0.6, "min_size": 45}),
    "slic": (slic, {"n_segments": 250, "compactness": 2, "convert2lab": True, "sigma": 1, "start_label": 0}),
    "quickshift": (quickshift, {"kernel_size": 5, "max_dist": 6, "ratio": 0.7}),
    "watershed": (_watershed, {"markers": 250, "compactness": 0.001})
}


def create_segments(img: np.ndarray, segmentation_method: str,
                    segmentation_settings: Optional[Dict[str, Any]]) -> np.ndarray:
    """
    create segments out of a loaded picture using different methods and settings

    Parameters
    ----------
    img : np.ndarray

    segmentation_method : str

    segmentation_settings : Dict[str, Any], optional

    Returns
    -------
    """
    segmentation_settings = segmentation_settings or {}

    try:
        segmentation_fn, default_settings = SEGMENTATION_METHODS[segmentation_method]
    except KeyError:
        raise ValueError(f"Unknown segmentation_method '{segmentation_method}'."
                         f" Available options: {list(SEGMENTATION_METHODS.keys())}")

    settings = {**default_settings, **segmentation_settings}

    _segment_mask = segmentation_fn(image=img, **settings)

    return _segment_mask - np.min(_segment_mask)


def generate_samples(segment_mask: np.ndarray, num_of_samples: int, p: float) -> np.ndarray:
    """
    determine which segments are displayed for each sample

    Parameters
    ----------
    segment_mask : np.ndarray
        The mask generated by `create_segments()`: An array of the same size as the image.

    num_of_samples : int
        The number of samples to generate

    p : float
        The probability for each segment to be replaced

    Returns
    -------
    samples : np.ndarray
        A two-dimensional array of size (num_of_samples, num_of_segments)
    """
    num_of_segments = np.unique(segment_mask).size

    return np.random.binomial(n=1, p=p, size=(num_of_samples, num_of_segments))


def generate_images(image: np.ndarray, segment_mask: np.ndarray, samples: np.ndarray,
                    background: Optional[Union[np.ndarray, int, float]] = None) -> np.ndarray:
    """Generate num_of_samples images that only contain the segments present in the sample.

    Parameters
    ----------
    image : np.ndarray
        The image to explain.

    segment_mask : np.ndarray
        The mask generated by `create_segments()`: An array of the same dimension and size as the image.

    samples : np.ndarray
        The samples generated by `generate_samples()`: An array of size (num_of_samples, num_of_segments).

    background : np.ndarray, int, or float, optional
        The background to replace the excluded segments with. Can be a single number or
        an array of the same dimension and size as the image.
        If not given, excluded segments are replaced with `0`.

    Returns
    -------
        An array of size (num_of_samples,
    """
    binary_segment_mask = np.zeros(shape=(samples.shape[0], image.shape[0], image.shape[1]), dtype=np.int)

    for k in range(binary_segment_mask.shape[0]):
        binary_segment_mask[k, :, :] = np.isin(segment_mask, np.nonzero(samples[k])).astype(np.int)

    images = binary_segment_mask[:, :, :, None] * image

    if background is not None:
        images += (1 - binary_segment_mask)[:, :, :, None] * background

    return images


def predict_images(images: np.ndarray, predict_fn: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
    """
    Parameters
    ----------
    images : np.ndarray
        Images as an array of dimension (num_of_samples, img_size_x, img_size_y, 3)

    predict_fn : Callable
        A function that takes an input of size (num_of_samples, img_size_x, img_size_y, 3)
        and returns an array of size (num_of_samples, num_of_classes).

    Returns
    -------
    An array of size (num_of_samples, num_of_classes)
    """
    return predict_fn(images)


LINEAR_MODELS = {
    "bayesian_ridge": BayesianRidge,
    "lasso": Lasso,
    "linear": LinearRegression
}


def weigh_segments(samples: np.ndarray, predictions: np.ndarray, label_idx: int,
                   model_type: str = "bayesian_ridge") -> np.ndarray:
    """Generating list of coefficients to weigh segments

    Parameters
    ----------
    samples : np.ndarray
    predictions : np.ndarray
    label_idx : int
    model_type : str

    Returns
    -------
    Array of size (num_of_segments,) where each entry corresponds to the segment's coefficient
    in the linear model.

    """
    try:
        linear_model = LINEAR_MODELS[model_type]()
    except KeyError:
        raise ValueError(f"Unknown model_type '{model_type}'. Available options: {list(LINEAR_MODELS.keys())}")

    linear_model.fit(samples, predictions[:, label_idx])

    return linear_model.coef_
