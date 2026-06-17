from webfluid.extensions.babel.utils import translation_resolver
from pathlib import Path


translations = translation_resolver(
    Path(__file__).parent, {
        "en": 0, "de": 1
    }
)
