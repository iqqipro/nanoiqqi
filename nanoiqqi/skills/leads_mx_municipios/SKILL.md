---
name: leads_mx_municipios
description: Catálogo de claves INEGI de municipios de México para la tool LeadsMx. Consultar cuando el usuario pida buscar establecimientos en una ciudad o municipio específico.
metadata: {"nanoiqqi":{"emoji":"🗺️","requires":{"tools":["LeadsMx"]}}}
---

# Catálogo de municipios (claves INEGI)

Consulta esta referencia cuando el usuario pida buscar establecimientos en una **ciudad o municipio específico** y necesites la clave de 3 dígitos para el parámetro `municipio` de LeadsMx.

## Cómo usar este catálogo

1. **Identifica el estado** del usuario → busca la clave de `entidad` (2 dígitos).
2. **Busca la ciudad** en la tabla del estado correspondiente → usa la clave de `municipio` (3 dígitos).
3. **Si la ciudad NO está en la tabla** → usa `municipio=0` (todos los municipios del estado) o usa `method=buscarEntidad` con `condicion=[nombre de la ciudad]` y `entidad=[clave del estado]`. **NUNCA inventes una clave de municipio.**
4. **Para buscar en toda la zona metropolitana** → usa `municipio=0` (abarca todos los municipios del estado).

## Estrategia recomendada según lo que el usuario pide

| El usuario dice… | Método recomendado | Parámetros |
|---|---|---|
| "buscar en [ciudad]" | `buscarEntidad` | condicion=[tipo de negocio o nombre de ciudad], entidad=[clave] |
| "establecimientos en [ciudad] de [tipo]" | `buscarEntidad` | condicion=[tipo], entidad=[clave] |
| "restaurantes en el municipio de [X]" | `buscarAreaActEstr` | entidad=[clave], municipio=[clave de tabla], nombre=0 |
| "empresas grandes en [ciudad]" | `buscarAreaActEstr` | entidad, municipio (de tabla o 0), estrato=6 o 7 |

**`buscarEntidad`** es la opción más segura cuando buscas por ciudad porque acepta el nombre de la ciudad como parte de `condicion` y no necesitas adivinar la clave de municipio.

---

## 01 – Aguascalientes

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 001 | Aguascalientes | 948,990 |
| 005 | Jesús María | 129,929 |
| 011 | San Francisco de los Romo | 61,997 |

## 02 – Baja California

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 004 | Tijuana | 1,922,523 |
| 002 | Mexicali | 1,049,792 |
| 001 | Ensenada | 443,807 |
| 005 | Playas de Rosarito | 126,890 |
| 003 | Tecate | 108,440 |

## 03 – Baja California Sur

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 008 | Los Cabos | 351,111 |
| 003 | La Paz | 292,241 |

## 04 – Campeche

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 002 | Campeche | 294,077 |
| 003 | Carmen | 248,845 |

## 05 – Coahuila

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 030 | Saltillo | 879,958 |
| 035 | Torreón | 720,848 |
| 018 | Monclova | 237,951 |
| 025 | Piedras Negras | 176,327 |
| 002 | Acuña | 163,058 |

## 06 – Colima

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 007 | Manzanillo | 191,031 |
| 002 | Colima | 157,048 |
| 010 | Villa de Álvarez | 149,762 |
| 009 | Tecomán | 116,305 |

## 07 – Chiapas

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 101 | Tuxtla Gutiérrez | 604,147 |
| 089 | Tapachula | 353,706 |
| 078 | San Cristóbal de las Casas | 215,874 |
| 019 | Comitán de Domínguez | 166,178 |

## 08 – Chihuahua

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 037 | Juárez | 1,512,450 |
| 019 | Chihuahua | 937,674 |
| 017 | Cuauhtémoc | 180,638 |
| 021 | Delicias | 150,506 |
| 032 | Hidalgo del Parral | 116,662 |

## 09 – Ciudad de México (alcaldías)

| Clave | Alcaldía | Población |
|-------|----------|-----------|
| 007 | Iztapalapa | 1,835,486 |
| 005 | Gustavo A. Madero | 1,173,351 |
| 010 | Álvaro Obregón | 759,137 |
| 012 | Tlalpan | 699,928 |
| 003 | Coyoacán | 614,447 |
| 015 | Cuauhtémoc | 545,884 |
| 014 | Benito Juárez | 422,294 |
| 016 | Miguel Hidalgo | 414,470 |
| 017 | Venustiano Carranza | 443,704 |
| 002 | Azcapotzalco | 400,161 |
| 006 | Iztacalco | 390,348 |
| 013 | Xochimilco | 442,178 |

## 10 – Durango

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 005 | Durango | 688,697 |
| 007 | Gómez Palacio | 372,750 |
| 012 | Lerdo | 163,313 |

## 11 – Guanajuato

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 020 | León | 1,721,215 |
| 017 | Irapuato | 592,953 |
| 007 | Celaya | 521,169 |
| 027 | Salamanca | 273,417 |
| 037 | Silao de la Victoria | 203,556 |
| 015 | Guanajuato | 194,500 |
| 003 | San Miguel de Allende | 174,615 |

## 12 – Guerrero

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 001 | Acapulco de Juárez | 779,566 |
| 029 | Chilpancingo de los Bravo | 283,354 |
| 035 | Iguala de la Independencia | 154,173 |
| 038 | Zihuatanejo de Azueta | 126,001 |

## 13 – Hidalgo

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 048 | Pachuca de Soto | 314,331 |
| 051 | Mineral de la Reforma | 202,749 |
| 077 | Tulancingo de Bravo | 168,369 |
| 069 | Tizayuca | 168,302 |

## 14 – Jalisco

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 120 | Zapopan | 1,476,491 |
| 039 | Guadalajara | 1,385,629 |
| 097 | Tlajomulco de Zúñiga | 727,750 |
| 098 | San Pedro Tlaquepaque | 687,127 |
| 101 | Tonalá | 569,913 |
| 067 | Puerto Vallarta | 291,839 |
| 070 | El Salto | 232,852 |
| 053 | Lagos de Moreno | 172,403 |

## 15 – Estado de México

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 033 | Ecatepec de Morelos | 1,645,352 |
| 058 | Nezahualcóyotl | 1,077,208 |
| 106 | Toluca | 910,608 |
| 057 | Naucalpan de Juárez | 834,434 |
| 031 | Chimalhuacán | 705,193 |
| 104 | Tlalnepantla de Baz | 672,202 |
| 121 | Cuautitlán Izcalli | 555,163 |
| 081 | Tecámac | 547,503 |

## 16 – Michoacán

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 053 | Morelia | 849,053 |
| 102 | Uruapan | 356,786 |
| 108 | Zamora | 204,860 |
| 052 | Lázaro Cárdenas | 196,003 |

## 17 – Morelos

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 007 | Cuernavaca | 378,476 |
| 011 | Jiutepec | 215,357 |
| 006 | Cuautla | 187,118 |
| 018 | Temixco | 122,263 |

## 18 – Nayarit

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 017 | Tepic | 425,924 |
| 020 | Bahía de Banderas | 187,632 |

## 19 – Nuevo León

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 039 | Monterrey | 1,142,994 |
| 006 | Apodaca | 656,464 |
| 026 | Guadalupe | 643,143 |
| 021 | General Escobedo | 481,213 |
| 031 | Juárez | 471,523 |
| 046 | San Nicolás de los Garza | 412,199 |
| 018 | García | 397,205 |
| 048 | Santa Catarina | 306,322 |

## 20 – Oaxaca

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 067 | Oaxaca de Juárez | 270,955 |
| 184 | San Juan Bautista Tuxtepec | 159,452 |
| 043 | Juchitán de Zaragoza | 113,570 |

## 21 – Puebla

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 114 | Puebla | 1,692,181 |
| 156 | Tehuacán | 327,312 |
| 132 | San Martín Texmelucan | 155,738 |
| 119 | San Andrés Cholula | 154,448 |

## 22 – Querétaro

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 014 | Querétaro | 1,049,777 |
| 016 | San Juan del Río | 297,804 |
| 011 | El Marqués | 231,668 |
| 006 | Corregidora | 212,567 |

## 23 – Quintana Roo

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 005 | Benito Juárez (Cancún) | 911,503 |
| 008 | Solidaridad (Playa del Carmen) | 333,800 |
| 004 | Othón P. Blanco (Chetumal) | 233,648 |
| 009 | Tulum | 46,721 |

## 24 – San Luis Potosí

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 028 | San Luis Potosí | 911,908 |
| 035 | Soledad de Graciano Sánchez | 332,072 |
| 013 | Ciudad Valles | 179,371 |

## 25 – Sinaloa

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 006 | Culiacán | 1,003,530 |
| 012 | Mazatlán | 501,441 |
| 001 | Ahome (Los Mochis) | 459,310 |
| 011 | Guasave | 289,370 |

## 26 – Sonora

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 030 | Hermosillo | 936,263 |
| 018 | Cajeme (Ciudad Obregón) | 436,484 |
| 043 | Nogales | 264,782 |
| 042 | Navojoa | 164,387 |

## 27 – Tabasco

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 004 | Centro (Villahermosa) | 683,607 |
| 002 | Cárdenas | 243,229 |
| 005 | Comalcalco | 214,877 |

## 28 – Tamaulipas

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 032 | Reynosa | 704,767 |
| 022 | Matamoros | 541,979 |
| 027 | Nuevo Laredo | 425,058 |
| 041 | Victoria (Ciudad Victoria) | 349,688 |
| 038 | Tampico | 297,562 |
| 003 | Altamira | 269,790 |

## 29 – Tlaxcala

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 033 | Tlaxcala | 99,896 |
| 013 | Huamantla | 98,764 |
| 005 | Apizaco | 80,725 |

## 30 – Veracruz

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 193 | Veracruz | 607,209 |
| 087 | Xalapa | 488,531 |
| 039 | Coatzacoalcos | 310,698 |
| 044 | Córdoba | 204,721 |
| 131 | Poza Rica de Hidalgo | 189,457 |

## 31 – Yucatán

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 050 | Mérida | 995,129 |
| 041 | Kanasín | 141,939 |
| 102 | Valladolid | 85,460 |

## 32 – Zacatecas

| Clave | Municipio | Población |
|-------|-----------|-----------|
| 010 | Fresnillo | 240,532 |
| 017 | Guadalupe | 211,740 |
| 056 | Zacatecas | 149,607 |

---

## Nota importante

Este catálogo incluye solo los municipios más poblados de cada estado (datos del Censo 2020). Si el usuario pregunta por un municipio que **no aparece aquí**, usa `municipio=0` (todos los municipios del estado) junto con `method=buscarEntidad` y `condicion=[nombre del municipio]`, o pregunta al usuario si conoce la clave INEGI de 3 dígitos.

Fuente: API del Catálogo Único de Claves Geoestadísticas de INEGI (https://gaia.inegi.org.mx/wscatgeo/v2/).
