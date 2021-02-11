import argparse
import os
import cv2
import random
import numpy as np
import math
import sys
import connections
import svgwrite
import shutil

# [INPUT_OUTPUT]
input_image = "./input/test1.jpg"
image_name = "test1.jpg"
output_dir = "."
create_png = 1
create_svg = 0
create_video = 1
show_step_images = 0
step_image_height = 800

# [VIDEO_PARAMETERS]
fps = 15
drawing_duration = 5
duration_of_final_image = 2.0
active_line_color = "200, 56, 56"
seconds_lines_remain_colored = 0.2
height = 1280
width = 720

# [DRAWING]
conf_no_of_layers = 30
conf_max_line_length_factor = 0.07
image_scale_factor = 0.8
conf_point_thresholds_prefactor = 0.00004
conf_point_thresholds_exponent = 2.6
random_seed = 800002


def get_empty_white_canvas(size_x=1920, size_y=1080):
    """
    This returns the array on which will be drawn.
    """
    img = 255 * np.ones((size_y, size_x, 3), dtype=np.uint8)
    return img


def get_prepared_image(source_image, scale_factor):
    """
    The original image is resized and turned into a
    grayscale image.
    """
    gray_image = cv2.cvtColor(source_image, cv2.COLOR_BGR2GRAY)
    new_width = int(round(scale_factor * gray_image.shape[1]))
    new_height = int(round(scale_factor * gray_image.shape[0]))
    new_size = (new_width, new_height)
    resized_image = cv2.resize(gray_image, new_size)
    return resized_image


def get_point_thresholds(no_of_layers, exponent, prefactor):
    """
    All layers have different threshold values.
    I found the results to be satisfying if the values obey
    a power law. The prefactor and the amplitude are
    defined in the options file.
    """
    return [math.pow(x, exponent) * prefactor for x in range(no_of_layers)]


def get_layer_points(current_max, point_threshold, prepared_image):
    """
    This function returns the points we will
    later connect with line segments.
    Random points may be put anywhere where the lightness
    of the image is below current_max. For each
    pixel that may potentially represent a point, we draw
    a random number. A point is only created if the random number
    if below point_threshold.
    """
    white_value = 255
    layer = prepared_image.copy()
    # find all positions where the image is darker than current_max
    layer[layer <= current_max] = 0
    layer[layer != 0] = white_value

    random_matrix = np.random.rand(*prepared_image.shape)
    layer[random_matrix > point_threshold] = white_value
    points = np.argwhere(layer == 0)
    points_tuples = [(p[1], p[0]) for p in points]
    return points_tuples


def resize_image_to_height(img, new_height):
    """
    This preserves the aspect ratio.
    """
    new_width = round(new_height * img.shape[1] / float(img.shape[0]))
    img_resized = cv2.resize(img, (int(new_width), new_height))
    return img_resized


def resize_image_to_width(img, new_width):
    """
    This preserves the aspect ratio.
    """
    new_height = round(new_width * img.shape[0] / float(img.shape[1]))
    img_resized = cv2.resize(img, (new_width, int(new_height)))
    return img_resized


def load_from_file():
    """
    Load some essential parameters which were defined
    in the external file.
    """
    scale_factor = float(image_scale_factor)
    no_of_layers = int(conf_no_of_layers)
    exponent = float(conf_point_thresholds_exponent)
    prefactor = float(conf_point_thresholds_prefactor)
    max_line_length_factor = float(conf_max_line_length_factor)
    infile_path = input_image
    return infile_path, scale_factor, no_of_layers, exponent, prefactor, max_line_length_factor


def create_scribble_art():
    infile_path, scale_factor, no_of_layers, exponent, \
        prefactor, max_line_length_factor = load_from_file()
    source_image = cv2.imread(infile_path)
    prepared_image = get_prepared_image(source_image, scale_factor)

    xmax, ymax = prepared_image.shape[1], prepared_image.shape[0]

    point_thresholds = get_point_thresholds(no_of_layers, exponent, prefactor)
    gray_value_step = 255.0 / len(point_thresholds)
    max_distance = max_line_length_factor * min(xmax, ymax)

    lines = []
    for layer_index in range(no_of_layers):
        print_progress("Create layers", layer_index, no_of_layers - 1)
        current_max = 255.0 - (layer_index + 1.0) * gray_value_step
        points = get_layer_points(
            current_max, point_thresholds[layer_index], prepared_image)

        if len(points) > 1:
            avg_distance = math.sqrt(float(xmax * ymax) / len(points))
            cell_width = min(avg_distance, max_distance)
            neighboring_points = connections.get_neighboring_points(
                points, cell_width, xmax, ymax)
            lines += get_line_segments_from_points(
                neighboring_points, cell_width)

        if bool(int(show_step_images)):
            canvas = put_lines_on_canvas(lines, prepared_image.shape)
            new_height = int(step_image_height)
            cv2.imshow("Current state",
                       resize_image_to_height(canvas, new_height))
            cv2.waitKey(1)
    print("")
    create_files(lines, prepared_image.shape)


def makesvg(lines):
    print("generating svg file...")
    out = '<svg xmlns="http://www.w3.org/2000/svg" version="1.1">'
    for l in lines:
        l = ",".join([str(p[0]*0.5)+","+str(p[1]*0.5) for p in l])
        out += '<polyline points="'+l+'" stroke="black" stroke-width="2" fill="none" />\n'
    out += '</svg>'
    return out


def create_files(lines, shape):
    if bool(create_png):
        canvas = put_lines_on_canvas(lines, shape)
        cv2.imwrite(output_dir + "/" + image_name + ".png", canvas)
    if bool(create_svg):
        # svg_drawing = svgwrite.Drawing(filename="./output/result.svg", size=(
        #     shape[1], shape[0]))
        # print(lines[0])
        f = open(output_dir + "/" + image_name + ".svg", 'w')
        f.write(makesvg(lines))
        f.close()
        # for start, end in lines:
        #     if len(start) == 2 and len(end) == 2:
        #         svg_drawing.add(svg_drawing.line(
        #             start, end, stroke=svgwrite.rgb(0, 0, 0, '%')))
        # svg_drawing.save()
    if bool(create_video):
        create_video(lines, shape)


def get_line_segments_from_points(neighboring_points, threshold):
    """
    Points i and i+1 will be connected if their
    distance is less than threshold.
    """
    lines = []
    for i in range(len(neighboring_points) - 1):
        start = neighboring_points[i]
        end = neighboring_points[i + 1]
        if connections.calc_distance(start, end) < threshold:
            lines.append((start, end))
    return lines


def put_lines_on_canvas(lines, shape):
    canvas = get_empty_white_canvas(shape[1], shape[0])
    for line in lines:
        start = line[0]
        end = line[1]
        stroke_scale = 1
        color = [0, 0, 0]
        cv2.line(canvas, start, end, color,
                 thickness=stroke_scale, lineType=8, shift=0)
    return canvas


def print_progress(msg, index, total):
    """
    This keeps the output on the same line.
    """
    text = "\r" + msg + " {:7d}/{:d}".format(index, total)
    sys.stdout.write(text)
    sys.stdout.flush()


def get_resized_img_for_video(img, video_width, video_height):
    """
    This preserves the aspect ratio of img.
    The background is filled with white pixels.
    """
    img_width = img.shape[1]
    img_height = img.shape[0]
    if img_width / float(img_height) <= video_width / float(video_height):
        resized_img = resize_image_to_height(img, video_height)
        resized_width = resized_img.shape[1]
        required_border = int(round(video_width - resized_width) / 2.0)
        video_frame = get_empty_white_canvas(video_width, video_height)
        video_frame[0:video_height, required_border:(
            resized_width + required_border)] = resized_img
    else:
        resized_img = resize_image_to_width(img, video_width)
        resized_height = resized_img.shape[0]
        required_border = int(round(video_height - resized_height) / 2.0)
        video_frame = get_empty_white_canvas(video_width, video_height)
        video_frame[required_border:(resized_height + required_border),
                    0:video_width] = resized_img
    return video_frame


def create_video(lines, shape):
    video_width = int(width)
    video_height = int(height)
    no_of_frames = int(drawing_duration * fps)
    no_of_lines_per_frame = int(len(lines) / (drawing_duration * fps)) + 1
    no_of_lines_per_second = int(len(lines) / drawing_duration)
    frames = []
    for i in range(no_of_frames):
        print_progress("Create frames", i, no_of_frames - 1)
        canvas = get_empty_white_canvas(shape[1], shape[0])
        line_index_a = i * no_of_lines_per_frame
        line_index_b = min(line_index_a + no_of_lines_per_frame, len(lines))
        for line_index, line in enumerate(lines[0:line_index_b]):
            start = line[0]
            end = line[1]
            if line_index > line_index_b - seconds_lines_remain_colored * no_of_lines_per_second:
                color = [
                    int(c) for c in active_line_color.split(",")]
                stroke_scale = 2
            else:
                stroke_scale = 1
                color = [0, 0, 0]
            cv2.line(canvas, start, end, color,
                     thickness=stroke_scale, lineType=8, shift=0)

        resized_canvas = get_resized_img_for_video(
            canvas, video_width, video_height)
        frames.append(resized_canvas)
    print("")

    # final frame
    final_canvas = put_lines_on_canvas(lines, shape)
    resized_final_canvas = get_resized_img_for_video(
        final_canvas, video_width, video_height)
    for i in range(int(fps * duration_of_final_image)):
        frames.append(resized_final_canvas)

    # write to file
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_dir + "/" + image_name + ".avi", fourcc,
                          fps, (video_width, video_height))
    for f in frames:
        out.write(f)
    out.release()


def delete_and_create_output_folder():
    """
    Each time the program is run, the previous output
    folder shall be deleted.
    """
    with open(os.devnull, 'wb') as quiet_output:
        if os.path.isdir("output"):
            shutil.rmtree("output")
        os.mkdir("output")


def set_seeds_of_rngs(seed):
    """
    You should be able to set the seeds of
    the employed random number generators
    if you want to reproduce an image.
    """
    random.seed(seed)
    np.random.seed(seed)


def main():
    """
    The program starts and ends here.
    """

    set_seeds_of_rngs(random_seed)
    create_scribble_art()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Convert image to sketch in png, svg and mp4.')
    parser.add_argument('-i', '--input', dest='input_image',
                        default='input_image', action='store', nargs='?', type=str,
                        help='Input image')

    parser.add_argument('-o', '--output', dest='output_dir',
                        default=output_dir, action='store', nargs='?', type=str,
                        help='Output directory.')

    args = parser.parse_args()

    input_image = args.input_image
    output_dir = args.output_dir

    image_name = input_image.split("/")[-1]
    image_name = image_name.split(".")[0]

    main()
