from importlib import metadata
from pathlib import Path


def main() -> None:
    packages = sorted(
        f"{dist.metadata['Name']}=={dist.version}"
        for dist in metadata.distributions()
        if dist.metadata.get("Name")
    )
    Path("environment-v0.3.lock").write_text("\n".join(packages) + "\n")


if __name__ == "__main__":
    main()
