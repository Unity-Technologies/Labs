import urllib.request
import os
import json
import glob
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional

from tqdm import tqdm
import pathlib


class TqdmUpTo(tqdm):
	"""Provides `update_to(n)` which uses `tqdm.update(delta_n)`."""
	def update_to(self, b=1, bsize=1, tsize=None):
		"""
		b  : int, optional
			Number of blocks transferred so far [default: 1].
		bsize  : int, optional
			Size of each block (in tqdm units) [default: 1].
		tsize  : int, optional
			Total size (in tqdm units). If [default: None] remains unchanged.
		"""
		if tsize is not None:
			self.total = tsize
		self.update(b * bsize - self.n)  # will also set self.n = b * bsize


def unzip(src_dir, local_dir, dataset_name, dataset_zipfile_name):
	target_dir = os.path.join(local_dir, dataset_name)
	zip_path = os.path.join(src_dir, dataset_zipfile_name)
	check_file = os.path.join(target_dir, ".check")

	if not os.path.isfile(zip_path):
		return False

	if os.path.isfile(check_file):
		return True

	print("extracting dataset", target_dir, "...")
	with zipfile.ZipFile(zip_path,"r") as zip_ref:
		zip_ref.extractall(local_dir)
	Path(check_file).touch()
	return True


class DatasetLoader():
	def __init__(self, dataset_path):
		self.known_datasets = {
			"deeppose_paper2021_minimixamo": "deeppose_paper2021_minimixamo.zip",
			"deeppose_paper2021_miniunity": "deeppose_paper2021_miniunity.zip",
		}
		self.dataset_path = dataset_path
		self.data_path = "data"

	def path_of(self, dataset_name: str) -> str:
		return os.path.join(self.dataset_path, dataset_name)

	def files_of(self, dataset_name: str) -> List[str]:
		return [f for f in glob.glob(os.path.join(self.path_of(dataset_name), "**/*"))
				if pathlib.Path(f).suffix != ".feather" and
				pathlib.Path(f).suffix != ".check" and
				pathlib.Path(f).suffix != ".cksum"]

	def pull(self, dataset_name: str) -> str:
		if self.is_available(dataset_name):
			return self.path_of(dataset_name)

		if not self.is_known(dataset_name):
			raise Exception("dataset not available: " + dataset_name)

		if not self._unzip(dataset_name):
			raise Exception("extracting dataset failed: " + dataset_name)

		return self.pull(dataset_name)

	def is_known(self, dataset_name: str) -> bool:
		return dataset_name in self.known_datasets

	def _unzip(self, dataset_name: str) -> bool:
		return unzip(self.data_path, self.dataset_path, dataset_name, self.known_datasets[dataset_name])

	def settings_file_of(self, dataset_name: str) -> Optional[str]:
		path = self.path_of(dataset_name)
		settings_file = os.path.join(path, "dataset_settings.json")
		if os.path.isfile(settings_file):
			return settings_file
		return None

	def is_valid(self, dataset_name: str) -> bool:
		dataset_files = self.files_of(dataset_name)
		return len(dataset_files) > 0

	def get_available_datasets(self) -> List[str]:
		return [os.path.basename(os.path.normpath(x)) for x in glob.glob(os.path.join(self.dataset_path, "*/"))]

	def is_available(self, dataset_name: str) -> bool:
		return dataset_name in self.get_available_datasets() and self.is_valid(dataset_name)

	def get_split(self, dataset_name: str) -> Dict[str, List[str]]:
		assert self.is_available(dataset_name), "Dataset is not available (did you pull it first?): " + dataset_name

		path = self.path_of(dataset_name)
		split_filepath = os.path.join(path, "split.json")
		with open(split_filepath) as f:
			data_splits = json.load(f)
			training = [self._build_path(path, x) for x in data_splits['training_files']]
			validation = [self._build_path(path, x) for x in data_splits['validation_files']]
			test = [self._build_path(path, x) for x in
					data_splits['test_files']] if 'test_files' in data_splits.keys() else None
		return {'Training': training, 'Validation': validation, 'Test': test, 'SplitFile': split_filepath, 'Settings': self.settings_file_of(dataset_name)}

	def get_settings(self, dataset_name: str) -> Dict[str, Any]:
		settings_filepath = self.settings_file_of(dataset_name)
		assert settings_filepath is not None, "Could not find settings file for dataset: " + dataset_name
		with open(settings_filepath) as f:
			settings = json.load(f)
		return settings

	def _build_path(self, path: str, filename: str) -> str:
		return os.path.normpath(os.path.join(path, filename))


class SplitFileDatabaseLoader(DatasetLoader):
	def __init__(self, dataset_path):
		super(SplitFileDatabaseLoader, self).__init__(dataset_path)

	def pull(self, dataset_name):
		if self.is_available(dataset_name):
			return self.split_file_of(dataset_name)

		if not self.is_known(dataset_name):
			raise Exception("dataset not available: " + dataset_name)

		if not self._unzip(dataset_name):
			raise Exception("extracting dataset failed: " + dataset_name)

		return self.pull(dataset_name)

	def build_path(self, path, filename):
		return os.path.normpath(os.path.join(path, filename))

	def split_file_of(self, dataset_name):
		path = self.path_of(dataset_name)

		with open(os.path.join(path, "split.json")) as f:
			data_splits = json.load(f)
			training = [self.build_path(path, x) for x in data_splits['training_files']]
			validation = [self.build_path(path, x) for x in data_splits['validation_files']]
			test = [self.build_path(path, x) for x in data_splits['test_files']] if 'test_files' in data_splits.keys() else None
		return {'Training' : training, 'Validation' : validation, 'Test': test, 'SplitFile': os.path.join(path, "split.json"), 'Settings': self.settings_file_of(dataset_name)}
