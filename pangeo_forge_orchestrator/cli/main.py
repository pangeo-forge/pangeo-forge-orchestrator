import typer

from . import bakery, catalog, feedstock, recipe

app = typer.Typer()

app.add_typer(bakery.app, name="bakery")
app.add_typer(catalog.app, name="catalog")
app.add_typer(feedstock.app, name="feedstock")
app.add_typer(recipe.app, name="recipe")
