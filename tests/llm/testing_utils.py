# Copyright (c) 2022 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import os
import shutil
import sys
import tempfile

import paddle

from tests.testing_utils import argv_context_guard, load_test_config


class LLMTest:
    config_path: str = None

    def setUp(self) -> None:
        self.root_path = "./llm"
        self.output_dir = tempfile.mkdtemp()
        self.inference_output_dir = tempfile.mkdtemp()
        sys.path.insert(0, self.root_path)

    def tearDown(self) -> None:
        sys.path.remove(self.root_path)
        shutil.rmtree(self.output_dir)
        shutil.rmtree(self.inference_output_dir)

    def run_predictor(self, config_params=None):
        config_params = config_params or {}
        # to avoid the same parameter
        paddle.utils.unique_name.switch()
        predict_config = load_test_config(self.config_path, "inference-predict")
        predict_config["output_file"] = os.path.join(self.output_dir, "predict.json")
        predict_config.update(config_params)
        predict_config["model_name_or_path"] = self.output_dir

        with argv_context_guard(predict_config):
            from predictor import predict

            predict()

        # to static
        paddle.disable_static()
        paddle.utils.unique_name.switch()
        config = load_test_config(self.config_path, "inference-to-static")
        config["output_path"] = self.inference_output_dir
        config["model_name_or_path"] = self.output_dir
        config.update(config_params)
        with argv_context_guard(config):
            from export_model import main

            main()

        # inference
        paddle.disable_static()
        config = load_test_config(self.config_path, "inference-infer")
        config["model_name_or_path"] = self.inference_output_dir
        config["output_file"] = os.path.join(self.inference_output_dir, "infer.json")
        enable_compare = config.pop("enable_compare", False)
        config.update(config_params)
        with argv_context_guard(config):
            from predictor import predict

            predict()

        # compare result
        if enable_compare:
            predict_result = self._read_result(predict_config["output_file"])
            infer_result = self._read_result(config["output_file"])
            assert len(predict_result) == len(infer_result)
            for predict_item, infer_item in zip(predict_result, infer_result):
                self.assertEqual(predict_item, infer_item)
