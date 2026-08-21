"""Add two numbers."""


def add(a: float, b: float) -> float:
    """Return the sum of ``a`` and ``b``."""
    return a + b


def main() -> None:
    first = float(input("Enter the first number: "))
    second = float(input("Enter the second number: "))
    print(f"{first} + {second} = {add(first, second)}")


if __name__ == "__main__":
    main()
