#  Copyright 2021 Collate
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""
ColumnValuesToBeNotNull validation implementation
"""
# pylint: disable=duplicate-code
import traceback
from datetime import datetime

from sqlalchemy import inspect

from metadata.generated.schema.tests.basic import (
    TestCaseResult,
    TestCaseStatus,
    TestResultValue,
)
from metadata.generated.schema.tests.testCase import TestCase
from metadata.orm_profiler.metrics.core import add_props
from metadata.orm_profiler.metrics.registry import Metrics
from metadata.orm_profiler.profiler.runner import QueryRunner
from metadata.utils.entity_link import get_decoded_column
from metadata.utils.logger import test_suite_logger

logger = test_suite_logger()


def column_values_to_not_match_regex(
    test_case: TestCase,
    execution_date: datetime,
    runner: QueryRunner,
) -> TestCaseResult:
    """
    Validate Column Values metric
    :param test_case: ColumnValuesToMatchRegex
    :param col_profile: should contain count and distinct count metrics
    :param execution_date: Datetime when the tests ran
    :param session: SQLAlchemy Session, for tests that need to compute new metrics
    :param table: SQLAlchemy Table, for tests that need to compute new metrics
    :param profile_sample: % of the data to run the profiler on
    :return: TestCaseResult with status and results
    """

    forbidden_regex = next(
        (
            param.value
            for param in test_case.parameterValues
            if param.name == "forbiddenRegex"
        )
    )
    not_like_count = add_props(expression=forbidden_regex)(Metrics.NOT_LIKE_COUNT.value)

    try:
        column_name = get_decoded_column(test_case.entityLink.__root__)
        col = next(
            (col for col in inspect(runner.table).c if col.name == column_name),
            None,
        )
        if col is None:
            raise ValueError(
                f"Cannot find the configured column {column_name} for test case {test_case.name}"
            )

        not_like_count_dict = dict(
            runner.dispatch_query_select_first(
                not_like_count(col).fn()
            )  # pylint: disable=abstract-class-instantiated
        )
        not_like_count_res = not_like_count_dict.get(Metrics.NOT_LIKE_COUNT.name)

    except Exception as exc:
        msg = (
            f"Error computing {test_case.name} for {runner.table.__tablename__}: {exc}"
        )
        logger.debug(traceback.format_exc())
        logger.warning(msg)
        return TestCaseResult(
            timestamp=execution_date,
            testCaseStatus=TestCaseStatus.Aborted,
            result=msg,
            testResultValue=[TestResultValue(name="notLikeCount", value=None)],
        )

    status = (
        TestCaseStatus.Success if not_like_count_res == 0 else TestCaseStatus.Failed
    )
    result = (
        f"Found {not_like_count_res} matching the forbidden regex pattern. Expected 0."
    )

    return TestCaseResult(
        timestamp=execution_date,
        testCaseStatus=status,
        result=result,
        testResultValue=[
            TestResultValue(name="notLikeCount", value=str(not_like_count_res))
        ],
    )
