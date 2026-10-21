from sklearn.linear_model import LinearRegression
import pandas
import os


class model:
    def __init__(self):
        self.lr = LinearRegression() ### creating linear regression model
        self.dataset_path = 'data/index.csv' ### dataset path

    def __valid_dataset(self, path=None):
        ### checking that the dataset does exists or does it have any content or not
        path = path or self.dataset_path
        if not os.path.isfile(path):
            return False
        if os.path.getsize(path) == 0:
            return False
        try:
            data = pandas.read_csv(path)
            return not data.empty
        except (pandas.errors.EmptyDataError, pandas.errors.ParserError, OSError):
            return False

    def load_data(self):
        ### loading dataset
        if not self.__valid_dataset():
            return [], False
        try:
            data = pandas.read_csv(self.dataset_path)
            return [data], True
        except (pandas.errors.EmptyDataError, pandas.errors.ParserError, OSError):
            return [], False