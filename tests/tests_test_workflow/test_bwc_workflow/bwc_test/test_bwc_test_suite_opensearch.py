# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.

import os
import unittest
from unittest.mock import MagicMock, call, patch

from git.git_repository import GitRepository
from manifests.build_manifest import BuildManifest
from manifests.bundle_manifest import BundleManifest
from manifests.test_manifest import TestManifest
from test_workflow.bwc_test.bwc_test_suite import InvalidTestConfigError, ScriptFinder
from test_workflow.bwc_test.bwc_test_suite_opensearch import BwcTestSuiteOpenSearch


@patch("os.makedirs")
@patch("os.chdir")
@patch.object(GitRepository, "__checkout__")
class TestBwcSuiteOpenSearch(unittest.TestCase):
    DATA = os.path.join(os.path.dirname(__file__), "data")
    BUILD_MANIFEST = os.path.join(DATA, "build_manifest.yml")
    BUNDLE_MANIFEST = os.path.join(DATA, "bundle_manifest.yml")
    TEST_MANIFEST = os.path.join(DATA, "test_manifest.yml")

    def setUp(self):
        os.chdir(os.path.dirname(__file__))
        self.bundle_manifest = BundleManifest.from_path(self.BUNDLE_MANIFEST)
        self.build_manifest = BuildManifest.from_path(self.BUILD_MANIFEST)
        self.test_manifest = TestManifest.from_path(self.TEST_MANIFEST)
        self.work_dir = "test_dir"
        self.test_recorder = MagicMock()
        self.save_logs = MagicMock()
        self.test_recorder.test_results_logs = self.save_logs

    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_execute(self, mock_test_recorder, *mock):
        test_config, component = self.__get_test_config_and_bundle_component("index-management")
        bwc_test_suite = BwcTestSuiteOpenSearch(
            self.work_dir,
            component,
            test_config,
            mock_test_recorder,
            self.bundle_manifest
        )

        mock_execute_bwctest_sh = MagicMock()
        mock_execute_bwctest_sh.return_value = "success"
        bwc_test_suite.execute_bwctest_sh = mock_execute_bwctest_sh

        bwc_test_suite.execute_tests()

        mock_execute_bwctest_sh.assert_has_calls([
            call("with-security"),
            call("without-security")
        ])

    @patch("os.path.exists", return_value=True)
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_execute_with_multiple_test_configs(self, mock_test_recorder, *mock):
        test_config, component = self.__get_test_config_and_bundle_component("job-scheduler")
        bwc_test_suite = BwcTestSuiteOpenSearch(
            self.work_dir,
            component,
            test_config,
            mock_test_recorder,
            self.bundle_manifest
        )
        mock_execute_bwctest_sh = MagicMock()
        mock_execute_bwctest_sh.return_value = "success"
        bwc_test_suite.execute_bwctest_sh = mock_execute_bwctest_sh

        test_results = bwc_test_suite.execute_tests()
        self.assertEqual(len(test_results), 2)
        self.assertTrue(test_results.failed)

        mock_execute_bwctest_sh.assert_has_calls([
            call("with-security"),
            call("without-security")
        ])

    @patch("os.path.exists", return_value=True)
    @patch.object(ScriptFinder, "find_bwc_test_script")
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_execute_with_working_directory(self, mock_test_recorder, mock_script_finder, *mock):
        test_config, component = self.__get_test_config_and_bundle_component("dashboards-reports")
        bwc_test_suite = BwcTestSuiteOpenSearch(
            self.work_dir,
            component,
            test_config,
            mock_test_recorder,
            self.bundle_manifest
        )

        mock_script_finder.return_value = "bwctest.sh"

        mock_execute_bwctest_sh = MagicMock()
        mock_execute_bwctest_sh.return_value = "success"
        bwc_test_suite.execute_bwctest_sh = mock_execute_bwctest_sh

        bwc_test_suite.execute_tests()

        mock_execute_bwctest_sh.assert_called_with("with-security")

    # Base class
    @patch("os.path.exists")
    @patch("test_workflow.bwc_test.bwc_test_suite.TestResultData")
    @patch("test_workflow.bwc_test.bwc_test_suite.GitRepository")
    @patch("test_workflow.bwc_test.bwc_test_suite.execute", return_value=True)
    def test_execute_bwctest_sh(self, mock_execute, mock_git, mock_test_result_data, mock_path_exists, *mock):
        test_config, component = self.__get_test_config_and_bundle_component("dashboards-reports")

        mock_find = MagicMock()
        mock_find.return_value = "./bwctest.sh"

        ScriptFinder.find_bwc_test_script = mock_find

        mock_git_object = MagicMock()
        mock_git_object.dir = "dir"
        mock_git.return_value = mock_git_object

        mock_execute.return_value = ("test_status", "test_stdout", "")

        mock_test_result_data_object = MagicMock()
        mock_test_result_data.return_value = mock_test_result_data_object

        mock_path_exists.return_value = True

        suite = BwcTestSuiteOpenSearch(
            self.work_dir,
            component,
            test_config,
            self.test_recorder,
            self.bundle_manifest
        )

        # call the test target
        status = suite.execute_bwctest_sh("with-security")

        self.assertEqual(status, "test_status")
        mock_execute.assert_called_once_with(
            './bwctest.sh',
            os.path.join("dir", "reports-scheduler"),
            True,
            False
        )

        mock_test_result_data.assert_called_once_with(
            "dashboards-reports",
            test_config,
            "test_status",
            "test_stdout",
            "",
            {
                'opensearch-bwc-test': os.path.join("dir", "reports-scheduler", "build", "reports", "tests", "bwcTest")
            }
        )
        self.save_logs.save_test_result_data.assert_called_once_with(mock_test_result_data_object)

    @patch("os.path.exists")
    @patch("test_workflow.bwc_test.bwc_test_suite.TestResultData")
    @patch("test_workflow.bwc_test.bwc_test_suite.GitRepository")
    @patch("test_workflow.bwc_test.bwc_test_suite.execute", return_value=True)
    def test_execute_bwctest_sh_script_do_not_exist(self, mock_execute, mock_git, mock_test_result_data, mock_path_exists, *mock):
        test_config, component = self.__get_test_config_and_bundle_component("dashboards-reports")
        mock_find = MagicMock()
        mock_find.return_value = "./bwctest.sh"

        ScriptFinder.find_bwc_test_script = mock_find

        mock_git_object = MagicMock()
        mock_git_object.dir = "https://test.github.com"
        mock_git.return_value = mock_git_object

        mock_path_exists.return_value = False

        suite = BwcTestSuiteOpenSearch(
            self.work_dir,
            component,
            test_config,
            self.test_recorder,
            self.bundle_manifest
        )

        # call the test target
        status = suite.execute_bwctest_sh("with-security")

        self.assertIsNone(status)

        mock_execute.assert_not_called()
        mock_test_result_data.assert_not_called()
        self.save_logs.assert_not_called()

    @patch("os.path.exists")
    @patch("test_workflow.bwc_test.bwc_test_suite.GitRepository")
    def test_is_security_enabled(self, mock_git, mock_path_exists, *mock):
        test_config, component = self.__get_test_config_and_bundle_component("dashboards-reports")
        mock_find = MagicMock()
        mock_find.return_value = "./bwctest.sh"

        ScriptFinder.find_bwc_test_script = mock_find

        mock_git_object = MagicMock()
        mock_git_object.dir = "https://test.github.com"
        mock_git.return_value = mock_git_object

        mock_path_exists.return_value = False

        suite = BwcTestSuiteOpenSearch(
            self.work_dir,
            component,
            test_config,
            self.test_recorder,
            self.bundle_manifest
        )

        self.assertTrue(suite.is_security_enabled("with-security"))
        self.assertFalse(suite.is_security_enabled("without-security"))

        with self.assertRaises(InvalidTestConfigError) as ctx:
            suite.is_security_enabled("random-config")

        self.assertEqual(str(ctx.exception), "Unsupported test config: random-config")

    @patch("test_workflow.bwc_test.bwc_test_suite.logging")
    @patch("os.path.exists")
    @patch("test_workflow.bwc_test.bwc_test_suite.GitRepository")
    def test_pretty_print_message(self, mock_git, mock_path_exists, mock_logging, *mock):
        test_config, component = self.__get_test_config_and_bundle_component("dashboards-reports")

        mock_find = MagicMock()
        mock_find.return_value = "./bwctest.sh"

        ScriptFinder.find_bwc_test_script = mock_find

        mock_git_object = MagicMock()
        mock_git_object.dir = "https://test.github.com"
        mock_git.return_value = mock_git_object

        mock_path_exists.return_value = False

        suite = BwcTestSuiteOpenSearch(
            self.work_dir,
            component,
            test_config,
            self.test_recorder,
            self.bundle_manifest
        )

        suite.pretty_print_message("test_message")

        mock_logging.info.assert_has_calls([
            call("==============================================="),
            call("test_message"),
            call("==============================================="),
        ])

    def __get_test_config_and_bundle_component(self, component_name):
        component = self.bundle_manifest.components[component_name]
        test_config = self.test_manifest.components[component.name]
        return test_config, component
