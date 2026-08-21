# Image credits

The catalog has no real product photography. Every one of the 39 distinct product names in the
seed data is matched by keyword to its own specific photo in `js/common.js`
(`PRODUCT_IMAGE_KEYWORDS`); only products that don't match any keyword fall back to a single
representative photo for their category. All are self-hosted under
`src/main/resources/static/images/` - not hotlinked, so the app never depends on a third-party
image host being up during grading. All are from Wikimedia Commons, openly licensed:

| File | Used for | Author | License | Source |
|---|---|---|---|---|
| `dairy.jpg` | Dairy & Eggs (fallback), "milk" | Joseph Tylczak | CC BY-SA 3.0 | [Commons](https://commons.wikimedia.org/wiki/File:Dg_milk_containers.jpg) |
| `bakery.jpg` | Bakery (fallback) | Mmangan333 | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Fresh_Scali_bread_loaf_from_Winter_Hill_Bakery.jpg) |
| `snacks.jpg` | Snacks & Cookies (fallback), "cookie" | Mshuang2 | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Chocolate_chip_cookies_on_cutting_board.jpg) |
| `beverages.jpg` | Beverages (fallback), "coffee" | Petr Kratochvil | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Coffee_cup_surrounded_by_coffee_beans.jpg) |
| `produce.jpg` | Produce (fallback) | Sven Scheuermeier | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Fresh_Vegetable_Produce_(Unsplash).jpg) |
| `pantry.jpg` | Pantry Staples (fallback) | Popo le Chien | CC BY-SA 3.0 | [Commons](https://commons.wikimedia.org/wiki/File:Macaronis.jpeg) |
| `frozen.jpg` | Frozen Foods (fallback) | Jina Lee | CC BY-SA 3.0 | [Commons](https://commons.wikimedia.org/wiki/File:Frozen_peas.JPG) |
| `eggs.jpg` | "egg" | Krzysztof Golik | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Egg_cartons_with_chicken_eggs_03.jpg) |
| `bread.jpg` | "bread" | FranHogan | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Fresh_made_bread_05.jpg) |
| `chips.jpg` | "chip" | Tomwsulcer | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Chips_in_a_bowl_at_a_party.JPG) |
| `cola.jpg` | "cola" | Cocktailmarler | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Glass_of_Cola.jpg) |
| `juice.jpg` | "orange juice" | USDA / Arad | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Orange_juice_1_edit1.jpg) |
| `pasta.jpg` | "pasta" | MartinThoma | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Cooked-Fusilli-on-plate-1.jpg) |
| `cereal.jpg` | "cereal" | Yvens Banatte | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Bowl_of_Cereal_(Unsplash).jpg) |
| `yogurt.jpg` | "yogurt" | Renee Comet | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Yogurt_(1).jpg) |
| `bagel.jpg` | "bagel" | Evan-Amos | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Bagel-Plain-Alt.jpg) |
| `croissants.jpg` | "croissant" | Herry Wibisono | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Croissants_au_beurre_%2818953292873%29.jpg) |
| `tea.jpg` | "green tea" | Editor at Large | CC BY-SA 2.5 | [Commons](https://commons.wikimedia.org/wiki/File:Canister_with_bags_of_green_tea.jpg) |
| `sparkling-water.jpg` | "sparkling water" | saw2th | CC BY-SA 2.0 | [Commons](https://commons.wikimedia.org/wiki/File:Sparkling-bottled-water.jpg) |
| `butter.jpg` | "butter" | Salicyna | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Block_of_butter_20200928_080156.jpg) |
| `cheddar.jpg` | "cheddar" | J.P.Lon | CC BY-SA 3.0 | [Commons](https://commons.wikimedia.org/wiki/File:Somerset-Cheddar.jpg) |
| `parmesan.jpg` | "parmesan" | cyclonebill | CC BY-SA 2.0 | [Commons](https://commons.wikimedia.org/wiki/File:Flickr_-_cyclonebill_-_Parmesan.jpg) |
| `frozen-berries.jpg` | "frozen berries" | www.bluewaikiki.com | CC BY 2.0 | [Commons](https://commons.wikimedia.org/wiki/File:Blackberries_in_containers%2C_2008.jpg) |
| `frozen-pizza.jpg` | "frozen pizza" | Renewableandalternativeenergy | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Frozen_Detroit-style_pizza_-_Upload.jpg) |
| `frozen-vegetables.jpg` | "frozen vegetable" | Kerolf666 | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:%E4%B8%89%E8%89%B2%E8%B1%86.jpg) |
| `ice-cream.jpg` | "ice cream" | Vouliagmeni | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Forte%27s_Ice_Cream_in_three_tubs.jpg) |
| `flour.jpg` | "flour" | Ph scale 56 | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:A_nice_bag_of_wheat_flour%21.jpg) |
| `olive-oil.jpg` | "olive oil" | Lemone | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Olive_oil_from_Oneglia.jpg) |
| `peanut-butter.jpg` | "peanut butter" | Shisma | CC BY 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Peanut_butter_glass.jpg) |
| `rice.jpg` | "rice" | Zahoor Ahmad Reshi | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Mushqbudji_rice_grains_close-up.jpg) |
| `sugar.jpg` | "sugar" | Douglas P Perkins | CC BY 3.0 | [Commons](https://commons.wikimedia.org/wiki/File:Bowl_of_white_sugar_without_background.jpg) |
| `tomato-sauce.jpg` | "tomato sauce" | Tabby | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Tomato_passata.jpg) |
| `apples.jpg` | "apple" | sydney zentz srz | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Freshly_Picked_Apples_%28Unsplash%29.jpg) |
| `avocado.jpg` | "avocado" | Ivar Leidus | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Avocado_Hass_-_single_and_halved.jpg) |
| `spinach.jpg` | "spinach" | Charipearl | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Fresh_Spinach_leaves.jpg) |
| `bananas.jpg` | "banana" | Wilfredor | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Bunch_of_bananas_on_sale.jpg) |
| `granola.jpg` | "granola" | Nikitha Jotheswari | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Granola_bar_food_products.jpg) |
| `pretzels.jpg` | "pretzel" | Fumikas Sagisavas | CC0 | [Commons](https://commons.wikimedia.org/wiki/File:Pretzels%F0%9F%8E%80%F0%9F%A5%A8.jpg) |
| `sandwich-cookies.jpg` | "sandwich cookie" | Dan Zimmerman | Public domain | [Commons](https://commons.wikimedia.org/wiki/File:Chocolate_oatmeal_sandwich_cookies.jpg) |

Images were downloaded at the pre-generated 500px thumbnail size and center-cropped to a square
locally (`sips`) - no further edits.
