from typing import List

from tensorflow.keras import activations, models, optimizers, losses
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau

from tensorflow.python.keras.layers import Input, Convolution1D, MaxPool1D, SpatialDropout1D, GlobalMaxPool1D, \
    Dropout, Dense, TimeDistributed
from tensorflow.python.keras.models import Model
from tensorflow.python.keras.callbacks import Callback


class ModelCNN:
    def __init__(self, classes_number, kernel_size: int = 3, pool_size: int = 2, dropout_rate: float = 0.01):
        self.__classes_number = classes_number
        self.__kernel_size = kernel_size
        self.__pool_size = pool_size
        self.__dropout_rate = dropout_rate

        self.__padding_valid = 'valid'
        self.__padding_same = 'same'
        self.__metrics = ['acc']

    def __generate_base_model(self) -> Model:
        sequence_input = Input(shape=(3000, 1))

        # twice convolutional layer
        sequence = Convolution1D(filters=32,
                                 kernel_size=self.__kernel_size,
                                 padding=self.__padding_valid,
                                 activation=activations.relu)(sequence_input)
        sequence = Convolution1D(filters=32,
                                 kernel_size=self.__kernel_size,
                                 padding=self.__padding_valid,
                                 activation=activations.relu)(sequence)

        for filters in [32, 32, 256]:
            # max pool and dropout
            sequence = MaxPool1D(pool_size=self.__pool_size, padding=self.__padding_valid)(sequence)
            sequence = SpatialDropout1D(rate=self.__dropout_rate)(sequence)

            # twice convolutional layer again
            sequence = Convolution1D(filters=filters,
                                     kernel_size=self.__kernel_size,
                                     padding=self.__padding_valid,
                                     activation=activations.relu)(sequence)
            sequence = Convolution1D(filters=filters,
                                     kernel_size=self.__kernel_size,
                                     padding=self.__padding_valid,
                                     activation=activations.relu)(sequence)
        # finale block
        sequence = GlobalMaxPool1D()(sequence)
        sequence = Dropout(rate=self.__dropout_rate)(sequence)

        sequence = Dense(units=64, activation=activations.relu)(sequence)

        # last dropout and model generation
        model = models.Model(inputs=sequence_input,
                             outputs=Dropout(rate=self.__dropout_rate)(sequence))

        # compile model
        model.compile(optimizer=optimizers.Adam(),
                      loss=losses.sparse_categorical_crossentropy,
                      metrics=self.__metrics)
        return model

    def generate_cnn_model(self) -> Model:
        sequence_input = Input(shape=(None, 3000, 1))

        # convolutional layer and dropout [1]
        sequence = TimeDistributed(self.__generate_base_model())(sequence_input)
        sequence = Convolution1D(filters=128,
                                 kernel_size=self.__kernel_size,
                                 padding=self.__padding_same,
                                 activation=activations.relu)(sequence)
        sequence = SpatialDropout1D(rate=self.__dropout_rate)(sequence)

        # convolutional layer and dropout [2]
        sequence = Convolution1D(filters=128,
                                 kernel_size=self.__kernel_size,
                                 padding=self.__padding_same,
                                 activation=activations.relu)(sequence)
        sequence = Dropout(rate=self.__dropout_rate)(sequence)

        # last convolution and model generation
        model = models.Model(inputs=sequence_input,
                             outputs=Convolution1D(filters=self.__classes_number,
                                                   kernel_size=self.__kernel_size,
                                                   padding=self.__padding_same,
                                                   activation=activations.softmax)(sequence))

        # compile model
        model.compile(optimizer=optimizers.Adam(),
                      loss=losses.sparse_categorical_crossentropy,
                      metrics=self.__metrics)
        return model


class ModelCallbacks:
    """
    Properties:
        - model_file_path: CNN model file path
        - monitor: possible values: 'val_acc', 'val_loss'
        - mode: possible values: 'max', 'min', 'auto'
        - es_patience: patience value for EarlyStopping
        - rlr_patience: patience value for ReduceLROnPlateau
    """
    def __init__(self,
                 model_file_path: str,
                 monitor: str = 'val_acc',
                 mode: str = 'max',
                 es_patience: int = 10,
                 rlr_patience: int = 5):
        self.__model_file_path = model_file_path
        self.__monitor = monitor
        self.__mode = mode
        self.__es_patience = es_patience
        self.__rlr_patience = rlr_patience

    def generate_model_callbacks(self) -> List[Callback]:
        """
        Generate model callbacks list
            - ModelCheckpoint - Callback to save the Keras model or model weights at some frequency
            - EarlyStopping - Stop training when a monitored metric has stopped improving
            - ReduceLROnPlateau - Reduce learning rate when a metric has stopped improving

        :return: list of callbacks
        """
        checkpoint = ModelCheckpoint(filepath=self.__model_file_path,
                                     monitor=self.__monitor,
                                     mode=self.__mode,
                                     verbose=1,
                                     save_best_only=True)
        early_stopping = EarlyStopping(monitor=self.__monitor,
                                       mode=self.__mode,
                                       patience=self.__es_patience,
                                       verbose=1)
        reduce_learning_rate = ReduceLROnPlateau(monitor=self.__monitor,
                                                 mode=self.__mode,
                                                 patience=self.__rlr_patience,
                                                 verbose=1)

        return [checkpoint, early_stopping, reduce_learning_rate]
