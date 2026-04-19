from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.utils import (
    find_unknown_fields,
    optional_str,
    optional_str_list,
    project_fields,
)


class UtilsTests(unittest.TestCase):
    def test_utils_package_reexports_mapping_and_coercion_helpers(self) -> None:
        projected = project_fields({"present": 1}, {"present": 0, "missing": list})

        self.assertEqual(projected, {"present": 1, "missing": []})
        self.assertEqual(find_unknown_fields({"a": 1, "b": 2}, {"a"}), ["b"])
        self.assertEqual(optional_str("value"), "value")
        self.assertEqual(optional_str_list(["a", 2]), ["a", "2"])

    def test_optional_str_normalizes_none_and_empty_string(self) -> None:
        self.assertIsNone(optional_str(None))
        self.assertIsNone(optional_str(""))
        self.assertEqual(optional_str(7), "7")

    def test_optional_str_list_rejects_non_list_inputs(self) -> None:
        self.assertIsNone(optional_str_list(None))
        with self.assertRaisesRegex(TypeError, "expected list value, got: str"):
            optional_str_list("not-a-list")


if __name__ == "__main__":
    unittest.main()
