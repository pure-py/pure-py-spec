import argparse
import pathlib
import sys

from .check_program import check_module, check_program, exit_code, format_program_rejection


def main() -> None:
    parser = argparse.ArgumentParser(prog="ourlang")
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--module", action="store_true")

    args = parser.parse_args()

    if not args.check:
        parser.error("running programs not yet implemented")

    rejection = check_module(args.path) if args.module else check_program(args.path)
    print(format_program_rejection(rejection, args.path))
    sys.exit(exit_code(rejection))


if __name__ == "__main__":
    main()
