import os.path

import numpy as np

from random import choice
from dataclasses import dataclass
from progressbar import progressbar
from sklearn.model_selection import train_test_split

from typing import Generator, Sized
from argparse import ArgumentParser
from tensorflow.python.keras.models import Model

from model import ModelCNN, ModelCallbacks
from statistics import save_plots_and_reports
from common.utils import *
from common.npz_parameters import *
from common.edf_parameters import *

H5_EXTENSION = '.h5'
DEFAULT_FILE_NAME = '(0_8__0_87)'

DEFAULT_MODEL_FILE_PATH = path.join(pardir, 'models', DEFAULT_FILE_NAME + H5_EXTENSION)
DEFAULT_REPORT_DIR_PATH = path.join(pardir, 'reports', DEFAULT_FILE_NAME)
DEFAULT_PLOT_DIR_PATH = path.join(pardir, 'plots', DEFAULT_FILE_NAME)

WINDOW_SIZE = 100


def parse_arguments():
    parser = ArgumentParser()

    parser.add_argument('--input_directory', type=str, default=NPZ_DIRECTORY_PATH,
                        help='Path to npz files')
    parser.add_argument('--model_file_path', type=str, default=DEFAULT_MODEL_FILE_PATH,
                        help='Path to model file')
    parser.add_argument('--report_dir_path', type=str, default=DEFAULT_REPORT_DIR_PATH,
                        help='Path to directory for reports')
    parser.add_argument('--plot_dir_path', type=str, default=DEFAULT_PLOT_DIR_PATH,
                        help='Path to directory for plots')
    parser.add_argument('--do_fit', type=bool, default=False,
                        help='set True, if needs to fit model, False load model from file')
    return parser.parse_args()


def train_test_validation_split(data: Sized) -> (Sized, Sized, Sized):
    train_val, test = train_test_split(data, test_size=0.15, random_state=1338)
    train, validation = train_test_split(train_val, test_size=0.1, random_state=1337)

    return train, test, validation


def load_npz_files(npz_paths: List[str]) -> dict:
    return {get_file_name_from_path(npz_path): np.load(npz_path) for npz_path in npz_paths}


def rescale_and_clip_array(array: np.array, scale: int = 0.05):
    array = array * scale
    array = np.clip(array, -scale * 100, scale * 100)
    return array


def data_to_generator(data: dict, count: int = 10, window_size: int = WINDOW_SIZE) -> Generator:
    """
    Transform data to generator of raw eeg and stages

    :param data: dictionary of date to transform
    :param count: generator iterations quantity
    :param window_size: size of data block (window)
    :return: raw eeg and stages
    """
    while True:
        chosen_data = data[choice(list(data.keys()))]

        assert len(chosen_data[RAW_VALUES_KEY]) == len(chosen_data[STAGE_VALUES_KEY])
        size = len(chosen_data[RAW_VALUES_KEY]) - window_size

        for i in range(count):
            idx = choice(range(size))
            raw_values = chosen_data[RAW_VALUES_KEY][idx:idx + window_size]
            stage_values = chosen_data[STAGE_VALUES_KEY][idx:idx + window_size]

            # increase the dimension of the vector and scale its values
            raw_values = prepare_raw_values_for_model(raw_values)

            # transpose the vector and increase the dimension by 1
            stage_values = np.expand_dims(stage_values, -1)
            stage_values = np.expand_dims(stage_values, 0)

            yield raw_values, stage_values


def prepare_raw_values_for_model(array: np.array):
    """
    Prepare the array for processing by the model:
         - change dimension
         - to scale
         - exclude unnecessary values

    :param array: array to modify
    :return: modified array
    """
    assert len(array.shape) <= 4

    # increase dimension by 1 until it reaches 4
    while len(array.shape) != 4:
        array = np.expand_dims(array, 0)

    return rescale_and_clip_array(array)


def convert_array_to_1d_list(array: np.array) -> list:
    return array.ravel().tolist()


@dataclass
class StagePredictionData:
    key: str
    raw_values: List[float]
    stage_values: List[int]
    predicted_stages: List[int]


def predict_stages(model: Model, test_data: dict) -> List[StagePredictionData]:
    prediction_data = []

    for test_data_key in progressbar(test_data):
        raw_values = test_data[test_data_key][RAW_VALUES_KEY]
        stage_values = test_data[test_data_key][STAGE_VALUES_KEY]

        assert len(raw_values) == len(stage_values)

        raw_values = prepare_raw_values_for_model(raw_values)

        prediction_data.append(
            StagePredictionData(
                key=test_data_key,
                raw_values=convert_array_to_1d_list(raw_values),
                stage_values=convert_array_to_1d_list(stage_values),
                predicted_stages=convert_array_to_1d_list(model.predict(raw_values).argmax(axis=-1))
            )
        )

    return prediction_data


def main():
    args = parse_arguments()

    create_directory(os.path.dirname(args.model_file_path))
    create_directory(args.report_dir_path)
    create_directory(args.plot_dir_path)

    # get the paths of all data files
    npz_files = get_files_in_directory(args.input_directory, NPZ_FILE_PATTERN)

    # create CNN model
    model = ModelCNN(STAGES_TYPES_NUMBER).generate_cnn_model()

    if args.do_fit:
        # split data into train, test and validation data
        train_files, test_files, validation_files = train_test_validation_split(npz_files)

        # load data from files
        train_data, test_data, validation_data = (
            load_npz_files(train_files),
            load_npz_files(test_files),
            load_npz_files(validation_files)
        )

        # train model
        model.fit(
            data_to_generator(train_data),
            validation_data=data_to_generator(validation_data),
            epochs=100,
            verbose=2,
            steps_per_epoch=1000,
            validation_steps=300,
            callbacks=ModelCallbacks(args.model_file_path).generate_model_callbacks()
        )
    else:
        test_data = load_npz_files(npz_files)

    # load model from file
    model.load_weights(args.model_file_path)

    # predict stages for test data
    prediction = predict_stages(model, test_data)

    # estimate prediction results
    stage_values_all, predicted_stages_all = [], []

    for item in prediction:
        stage_values_all += item.stage_values
        predicted_stages_all += item.predicted_stages

        save_plots_and_reports(
            stage_values=item.stage_values,
            predicted_stages=item.predicted_stages,
            file_name=item.key,
            plot_dir_path=args.plot_dir_path,
            report_dir_path=args.report_dir_path
        )

    # summarize results
    save_plots_and_reports(
        stage_values=stage_values_all,
        predicted_stages=predicted_stages_all,
        file_name='summary',
        plot_dir_path=args.plot_dir_path,
        report_dir_path=args.report_dir_path
    )


if __name__ == '__main__':
    main()
