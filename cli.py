"""Console script for automonkey."""
import sys
import click


@click.command()
def main(args=None):
    """Console script for automonkey."""
    click.echo("Replace this message by putting your code into "
               "automonkey.cli.main")
    click.echo("See click documentation at https://click.palletsprojects.com/")
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
