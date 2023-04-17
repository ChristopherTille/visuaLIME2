import warnings
from typing import List, Literal, Optional, Tuple, Union

import numpy as np
from PIL import Image
from PIL.ImageColor import getrgb


def select_segments(
    segment_weights: np.ndarray,
    segment_mask: np.ndarray,
    coverage: Optional[float] = None,
    num_of_segments: Optional[int] = None,
    min_coverage: float = 0.0,
    max_coverage: float = 1.0,
    min_num_of_segments: int = 0,
    max_num_of_segments: Optional[int] = None,
) -> np.ndarray:
    """Select the segments to color.

    Segments are selected in the order of descending weight until the desired `coverage`
    or `num_of_segments` is reached.
    Exactly one of these parameters has to be specified when calling the function.

    Parameters
    ----------
    segment_weights : np.ndarray
        The weights produced by :meth:`visualime.lime.weigh_segments`:
        A one-dimensional array of length `num_of_segments`.

    segment_mask : np.ndarray
        The mask generated by :meth:`visualime.lime.create_segments`:
        An array of shape `(image_width, image_height)`.

    coverage : float, optional
        The coverage of the selected segments relative to the area of the image.
        Either `coverage` or `num_of_segments` must be specified.

        A warning will be given if reaching the coverage threshold requires selection
        of all segments.

    num_of_segments : int, optional
        The number of segments to select.
        Either `num_of_segments` or `coverage` must be specified.

    min_coverage : float, default 0.0
        The minimum coverage of the selected segments relative to the area of the image.
        If the specified `num_of_segments` does not reach this coverage, additional
        segments will be selected until this minimum coverage is reached.

        A warning will be given if reaching the coverage threshold requires selection
        of all segments.

    max_coverage : float, default 1.0
        The maximum coverage of the selected segments relative to the area of the image.
        If the specified `num_of_segments` exceeds this coverage, segments will
        be removed from the selection until the coverage is below this maximum.

        At least one segment will be returned even if the maximum coverage is exceeded.
        In this case, a warning will be given.

    min_num_of_segments : int, default 0
        The minimum number of segments to select.
        Even if the specified `coverage` is reached with fewer segments, at least
        this minimum number of segments are returned.

    max_num_of_segments : int, optional
        The maximum number of segments to select.
        Even if more segments would be required to reach the specified `coverage`,
        at most this maximum number of segments are returned.

    Returns
    -------
    np.ndarray
        A one-dimensional array that contains the selected segment indices.

    Notes
    -----
    To select the segments with the lowest weights, pass the `segment_weights` array
    with negative sign:

    >>> select_segments(segment_weights=-segment_weights, ...)
    """
    if coverage is None and num_of_segments is None:
        raise ValueError("Either coverage or num_of_segments has to be specified.")

    if coverage is not None and num_of_segments is not None:
        raise ValueError("Only either coverage or num_of_segments can be given.")

    if min_coverage >= max_coverage:
        raise ValueError("min_coverage has to be strictly smaller than max_coverage.")

    max_segment_idx = int(np.max(segment_mask))
    total_num_of_segments = max_segment_idx + 1

    if segment_weights.shape[0] != total_num_of_segments:
        raise ValueError(
            f"The number of segment_weights ({segment_weights.shape[0]}) does not match "
            f"the number of segments ({total_num_of_segments}) in the provided segment_mask. "
            f"Note that segments need to be numbered consecutively, starting at 0."
        )

    max_num_of_segments = max_num_of_segments or total_num_of_segments

    if min_num_of_segments >= max_num_of_segments:
        raise ValueError(
            "min_num_of_segments has to be strictly smaller than max_num_of_segments."
        )

    _area = segment_mask.shape[0] * segment_mask.shape[1]

    ordered_segments = np.argsort(-segment_weights)

    if coverage is not None:
        coverage = min(coverage, max_coverage, 1.0)
        coverage = max(coverage, min_coverage, 0.0)

        for i in range(max_segment_idx):
            _selected_segments = ordered_segments[: i + 1]
            if np.isin(segment_mask, _selected_segments).sum() / _area >= coverage:
                num_of_segments = i + 1
                break
        else:
            warnings.warn(
                f"Need to select all {max_num_of_segments} segments to reach desired "
                f"coverage threshold of {coverage}.",
                RuntimeWarning,
            )
            num_of_segments = max_num_of_segments

    if num_of_segments is not None:
        num_of_segments = min(num_of_segments, max_num_of_segments)
        num_of_segments = max(num_of_segments, min_num_of_segments)

        _selected_segments = ordered_segments[:num_of_segments]

        if np.isin(segment_mask, _selected_segments).sum() / _area > max_coverage:
            selected_segments = select_segments(
                segment_weights=segment_weights,
                segment_mask=segment_mask,
                coverage=max_coverage,
            )
            if np.isin(segment_mask, selected_segments).sum() / _area > max_coverage:
                warnings.warn(
                    f"Despite selecting only {selected_segments.shape[0]} segments, "
                    f"coverage still exceeds the desired maximum of {max_coverage:.2f}."
                )
        elif np.isin(segment_mask, _selected_segments).sum() / _area < min_coverage:
            selected_segments = select_segments(
                segment_weights=segment_weights,
                segment_mask=segment_mask,
                coverage=min_coverage,
            )
        else:
            selected_segments = _selected_segments

    # TODO: Figure out why PyCharm believes that the return value could potentially be None
    return selected_segments


def _get_color(color: Union[str, Tuple[int, int, int]], opacity: float) -> np.ndarray:
    """Convert a color specified by name or RGB tuple into an RGBA color.

    Note that `color` can also be an RGB(A) string in various formats.
    """
    rgb_color: Union[Tuple[int, int, int], Tuple[int, int, int, int]]

    if isinstance(color, str):
        try:
            rgb_color = getrgb(color)
        except ValueError:
            raise ValueError(
                f"Unknown color '{color}'. See documentation for available colors."
            )
    else:
        rgb_color = color

    _rgba = np.array(list(rgb_color[:3]) + [int(255 * opacity)]).astype(int)

    if np.any(_rgba < 0) or np.any(_rgba > 255):
        raise ValueError(
            f"Channel values must be between 0 and 255. Got {tuple(_rgba)} instead."
        )

    return _rgba


def generate_overlay(
    segment_mask: np.ndarray,
    segments_to_color: Union[np.ndarray, List[int]],
    color: Union[str, Tuple[int, int, int]],
    opacity: float,
) -> np.ndarray:
    """Generate a semi-transparent overlay with selected segments colored.

    Parameters
    ----------
    segment_mask : np.ndarray
        The mask generated by :meth:`visualime.lime.create_segments`:
        An array of shape `(image_width, image_height)`.

    segments_to_color : np.ndarray or list of ints
        An array that contains the integer segment numbers of the segments to color.
        Usually obtained through :meth:`visualime.visualize.select_segments`.

    color : str or int 3-tuple (RGB)
        The color for the segments.
        Can be given as a color name or an RGB tuple.

        Color names are parsed through :meth:`PIL.ImageColor.getrgb`.
        To obtain a list of available color names, run:

        >>> from PIL.ImageColor import colormap, getrgb
        >>> for name, code in colormap.items(): print(name, getrgb(code))

        Note that while it is possible to pass an RGBA tuple, only the RGB values
        will be considered.
        The alpha channel is controlled exclusively via the `opacity` parameter.

    opacity : float
        The opacity of the overlay as a number between `0.0` (fully transparent)
        and `1.0` (fully opaque).

    Returns
    -------
    np.ndarray
        An array of shape `(image_width, image_height, 4)` representing an RGBA image.
    """
    mask = np.isin(segment_mask, segments_to_color)
    channel_mask = np.dstack((mask, mask, mask, mask))
    return channel_mask * _get_color(color, opacity)


def scale_opacity(
    overlay: np.ndarray,
    segment_mask: np.ndarray,
    segment_weights: np.ndarray,
    segments_to_color: Union[np.ndarray, List[int]],
    relative_to: Union[Literal["max"], float] = "max",
    exponent: float = 1.0,
    max_opacity: float = 1.0,
) -> np.ndarray:
    """Set the opacity of each segment according to its weight.

    Segments with a higher (absolute) weight will be more opaque than segments with a lower weight.

    Parameters
    ----------
    overlay : np.ndarray
        The output of :meth:`visualime.visualize.generate_overlay`:
        An array of shape `(image_width, image_height, 4)` representing an RGBA image.

    segment_mask : np.ndarray
        The mask generated by :meth:`visualime.lime.create_segments`:
        An array of shape `(image_width, image_height)`.

    segment_weights : np.ndarray
        The weights produced by :meth:`visualime.lime.weigh_segments`:
        A one-dimensional array of length `num_of_segments`.

    segments_to_color : np.ndarray or list of ints
        An array that contains the integer segment numbers of the segments to color.
        Usually obtained through :meth:`visualime.visualize.select_segments`.

    relative_to : {float, "max"}, default "max"
        The relative weight to consider the maximum weight when determining the opacity of a segment.

        Can either be a number between `0.0` (exclusive) and `1.0`, with `1.0` corresponding to the
        maximum weight that is theoretically possible for a segment.

        Alternatively, if set to `"max"` (the default), the maximum absolute weight of any segment is
        considered as the maximum value. Note that for this calculation, all segments are considered,
        even if they are not included in `segments_to_color`.

    exponent: int, default 1.0
        The exponent used when calculating the opacity of a given segment.

        A segment's opacity is calculated as `(segment_weight/reference)**exponent`,
        where `segment_weight` is the normalized weight of the segment.

        The default value for the exponent is 1.0, resulting in linear scaling of the opacity.
        An exponent smaller than 1.0 gives more emphasis to smaller weights, while an
        exponent larger than 1.0 gives more emphasis to larger weights.

    max_opacity : float, default 1.0
        The maximum opacity of the overlay as a number between `0.0` and `1.0`.

    Returns
    -------
    np.ndarray
        An array of shape `(image_width, image_height, 4)` representing an RGBA image.

        Note that this function does not modify the original `overlay` but returns a new array.
    """
    rescaled_weights = np.abs(segment_weights / np.linalg.norm(segment_weights))

    try:
        relative_to = float(relative_to)
    except ValueError:
        pass

    if relative_to == "max":
        reference = np.max(rescaled_weights)
    elif isinstance(relative_to, float):
        reference = max(1e-6, min(relative_to, 1.0))
    else:
        raise ValueError(f"Invalid value '{relative_to}' for 'relative_to'.")

    new_opacity = np.clip(
        255 * np.clip((rescaled_weights / reference) ** exponent, 0, 1),
        0,
        max_opacity * 255,
    ).astype(np.uint8)

    new_overlay = np.ndarray.copy(overlay)

    for segment_id in segments_to_color:
        mask = segment_mask == segment_id
        new_overlay[mask, 3] = new_opacity[segment_id]

    return new_overlay


def scale_overlay(overlay: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    """Scale the overlay to a given size.

    Parameters
    ----------
    overlay : np.ndarray
        The output of :meth:`visualime.visualize.generate_overlay`:
        An array of shape `(image_width, image_height, 4)` representing an RGBA image.

    shape : tuple of ints
        The size to scale the overlay to.

    Returns
    -------
    np.ndarray
        An array of shape `(image_width, image_height, 4)` representing an RGBA image.

        Note that this function does not modify the original `overlay` but returns a new array.
    """
    return np.array(
        Image.fromarray(overlay, mode="RGBA").resize(shape, resample=Image.NEAREST)
    )


def mark_boundaries(
    image: np.ndarray,
    segment_mask: np.ndarray,
    color: Union[str, Tuple[int, int, int]] = "red",
    opacity: float = 1.0,
) -> np.ndarray:
    """Mark the boundaries of the segments in the image.

    Parameters
    ----------
    image : np.ndarray
        The image to mark the boundaries of the segments in.
        The image must be an array of shape `(image_width, image_height, 3)`.
        The image will be modified in-place.

    segment_mask : np.ndarray
        The mask generated by :meth:`visualime.lime.create_segments`:
        An array of shape `(image_width, image_height)`.

    color : str or int 3-tuple (RGB), default "red"
        The color for the boundaries.
        Can be given as a color name or an RGB tuple.

        Color names are parsed through :meth:`PIL.ImageColor.getrgb`.
        To obtain a list of available color names, run:

        >>> from PIL.ImageColor import colormap, getrgb
        >>> for name, code in colormap.items(): print(name, getrgb(code))

        Note that while it is possible to pass an RGBA tuple, only the RGB values
        will be considered, the opacity will be determined by the `opacity` parameter.

    opacity : float, default 1.0
        The opacity of the boundaries as a number between `0.0` and `1.0`.

    Returns
    -------
    np.ndarray
        An array of shape `(image_width, image_height, 3)` representing an RGB image.
    """
    rgb_color = _get_color(color, opacity)[:3]

    if image.shape[:2] != segment_mask.shape:
        raise ValueError(
            f"The shape of the mask ({segment_mask.shape}) does not match "
            f"the shape of the image ({image.shape[:2]})"
        )

    for i in range(1, image.shape[0]):
        for j in range(1, image.shape[1]):
            if segment_mask[i, j] != segment_mask[i - 1, j]:
                image[i, j] = image[i, j] * (1 - opacity) + rgb_color * opacity
            if segment_mask[i, j] != segment_mask[i, j - 1]:
                image[i, j] = image[i, j] * (1 - opacity) + rgb_color * opacity

    return image


# TODO: Add more functions to normalize the segments weights, deal with outliers etc.


def smooth_weights(segment_weights: np.ndarray) -> np.ndarray:
    """Smooth the `segment_weights` by applying the sigmoid function.

    Parameters
    ----------
    segment_weights : np.ndarray
        The weights produced by :meth:`visualime.lime.weigh_segments`:
        A one-dimensional array of length `num_of_segments`.

    Returns
    -------
    np.ndarray
        A smoothed copy of the `segment_weights`.
    """
    return 1 / (1 + np.exp(-segment_weights))
