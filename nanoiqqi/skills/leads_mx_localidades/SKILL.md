---
name: leads_mx_localidades
description: Guía para buscar establecimientos por localidad en México con la tool LeadsMx. Usar cuando el usuario pida buscar en una localidad, colonia o zona específica.
metadata: {"nanoiqqi":{"emoji":"📌","requires":{"tools":["LeadsMx"]}}}
---

# Localidades en la API DENUE

Las **localidades** son el nivel geográfico más fino (debajo de municipio) en el sistema INEGI. Se identifican con una clave de **4 dígitos** dentro de cada municipio.

## Regla principal

**NUNCA inventes una clave de localidad.** México tiene decenas de miles de localidades y sus claves no son intuitivas. Si no tienes la clave exacta, usa siempre `localidad=0` (todas las localidades del municipio).

## Cómo manejar búsquedas por localidad, colonia o zona

| El usuario dice… | Qué hacer |
|---|---|
| "buscar en [colonia/barrio]" | Usa `method=buscar` con `condicion=[nombre de colonia], [tipo de negocio]`. El método `buscar` busca en nombre de colonia como parte de la condición. |
| "establecimientos en [localidad rural]" | Usa `method=buscarEntidad` con `condicion=[nombre de localidad]` y la `entidad` correspondiente. |
| "buscar en localidad 0001 del municipio 039" | Solo si el usuario da la clave numérica explícita, usa `localidad=0001` en `buscarAreaActEstr`. |
| "buscar en [zona/región]" sin clave | Usa `localidad=0` (todas) y filtra por `condicion` o `nombre` con la palabra de la zona. |

## Estructura jerárquica INEGI

```
Entidad (2 dígitos)  →  Municipio (3 dígitos)  →  Localidad (4 dígitos)
      14 (Jalisco)           039 (Guadalajara)          0001 (cabecera)
```

- La clave `0001` generalmente corresponde a la **cabecera municipal** (la ciudad principal del municipio).
- Claves `0002` en adelante son localidades secundarias, rurales o suburbanas.
- Para ciudades grandes, la cabecera (`0001`) abarca la mayor parte de la zona urbana.

## Cuándo SÍ usar localidad

- Cuando el usuario proporciona explícitamente la clave de 4 dígitos.
- Cuando quieres filtrar solo la cabecera municipal: usa `localidad=0001`.

## Cuándo NO usar localidad (usar 0)

- Cuando buscas en toda una ciudad o municipio → `localidad=0`.
- Cuando el usuario menciona una colonia → usa `condicion` con el nombre de la colonia en `buscar` o `buscarEntidad`.
- Cuando no tienes la clave numérica → `localidad=0`, **nunca adivines**.

## Parámetros AGEB y Manzana

Debajo de localidad existen dos niveles aún más finos:

- **AGEB** (4 dígitos): Área Geoestadística Básica. Subdivide localidades urbanas en bloques. Usa `ageb=0` salvo que el usuario proporcione la clave.
- **Manzana** (3 dígitos): Manzana catastral dentro de un AGEB. Usa `manzana=0` salvo que el usuario proporcione la clave.

**Regla:** Para AGEB y Manzana, usa siempre `0` (omitir) a menos que el usuario dé la clave exacta. No existen catálogos prácticos para buscar estas claves por nombre.

## Alternativas cuando no tienes la clave de localidad

1. **`buscarEntidad`** con `condicion=[nombre del lugar]` → busca la palabra en todos los campos (colonia, localidad, municipio, etc.).
2. **`buscar`** con `condicion=[nombre del lugar], [tipo de negocio]` → búsqueda general que incluye nombre de colonia y localidad.
3. **`buscarAreaActEstr`** con `localidad=0` → todos los establecimientos del municipio, sin restricción de localidad.

Estas alternativas son más seguras y producen buenos resultados sin necesidad de conocer claves numéricas.
