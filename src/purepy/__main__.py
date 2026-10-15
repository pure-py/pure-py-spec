import argparse
import pathlib
import sys

from .check_module import check_file, format_result
from .check_program import check_program


def main() -> None:
    parser = argparse.ArgumentParser(prog="purepy")
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--module", action="store_true")

    args = parser.parse_args()

    if not args.check:
        parser.error("running programs is not supported yet; use --check")

    if args.module:
        result = check_file(str(args.path))
        print(format_result(result, str(args.path)))
    else:
        result = check_program(args.path)
        if result is not None:
            print(result.msg)

    sys.exit(0 if result is None else result.exit_code)


if __name__ == "__main__":
    main()
