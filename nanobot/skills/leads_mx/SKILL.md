---
name: leads_mx
description: Buscar establecimientos comerciales en México con la API DENUE (INEGI). Usa la tool LeadsMx eligiendo el método adecuado según la intención (contar, buscar por radio, por nombre, por estado, por actividad/ubicación/tamaño, o detalle por ID).
metadata: {"nanobot":{"emoji":"📍","always":true,"requires":{"tools":["LeadsMx"]}}}
---

# LeadsMx – Establecimientos en México (DENUE)

Usa la tool **LeadsMx** cuando el usuario pida buscar negocios, establecimientos o empresas en México. Elige el método según la **intención** del usuario y adapta los parámetros a **lo que realmente pide**; no inventes datos que no te haya dado.

---

## Reglas para evitar alucinaciones

- **Siempre envía el parámetro `method`.** Sin él la tool falla. Si quieres listar por estado/ciudad usa `buscarEntidad` o `buscarAreaActEstr` según la tabla de criterios.
- **NUNCA envíes cadenas vacías** (`""`) en entidad, municipio, localidad, nombre, condicion, etc. Usa siempre:
  - **entidad:** `"00"` = todo el país, o una clave de 2 dígitos del catálogo (ej. `"15"` Estado de México).
  - **municipio / localidad / sector / rama / clase / nombre:** `"0"` = todos / omitir.
- **No inventes nunca:** token, IDs de establecimiento, coordenadas (lat/lon), códigos SCIAN ni claves de entidad/municipio que no estén en esta skill.
- **Tipo de negocio en palabras:** "restaurantes", "farmacias" → usa **condicion** en `buscar` o `buscarEntidad`. No inventes sector/rama/clase; si no conoces el código SCIAN usa `"0"` en esos campos.
- **Entidad (estado):** Puedes enviar la **clave de 2 dígitos** (01–32) o el **nombre del estado o alias** (ej. "Jalisco", "CDMX", "Estado de México"); la tool lo traduce a clave. Si no sabes la clave, usa `entidad=00` o escribe el nombre del estado.
- **Coordenadas:** Solo si el usuario da lat/lon. Si pide "cerca de X" sin coordenadas, usa solo `condicion` o pide ubicación.
- **Ficha:** Solo con un `id` que el usuario dio o que salió en una respuesta previa de LeadsMx.

---

## Libertad para adaptar la consulta

- **Interpreta la intención:** Puedes elegir el método que mejor encaje (contar vs listar, por nombre vs por tipo, por estado vs por radio, etc.) aunque el usuario no diga el nombre del método.
- **Traduce palabras a parámetros:** "Restaurantes en Jalisco" → `buscarEntidad` con `condicion=restaurante`, `entidad=14`. "Cuántas farmacias en CDMX" → `cuantificar` con `actividad=0` o palabra en area/condicion según lo que permita el método; si cuantificar no acepta palabra, usa `actividad=0` y explica que el conteo es general, o usa otro método que sí acepte condición.
- **Valores por defecto razonables:** Si no especifica paginación, usa por ejemplo `registro_inicial=1`, `registro_final=50`. Si no especifica estado, usa `00` cuando el método lo permita. Si no especifica tamaño, usa `estrato=0`.
- **Cuando falte algo crítico:** Si para el método elegido falta un dato obligatorio (ej. ID para ficha, o estado concreto para una búsqueda estatal), pregunta al usuario o ofrece una alternativa (ej. búsqueda nacional con `entidad=00`).

---

## Cuándo usar (frases típicas)

- "buscar establecimientos en…", "negocios en [ciudad/estado]"
- "empresas en México", "listado de empresas por sector"
- "denue", "directorio de negocios"
- "cuántos restaurantes hay en…", "cuántas farmacias en Jalisco"
- "buscar por nombre OXXO", "todas las sucursales de [marca]"
- "establecimientos cerca de [dirección/coordenadas]"
- "detalle de un establecimiento", "ficha de empresa con ID"
- "microempresas en [lugar]", "empresas de 50+ empleados"

---

## Qué método usar (criterios)

| Intención / situación del usuario | Método | Parámetros clave |
|-----------------------------------|--------|------------------|
| "Quiero saber **cuántos** hay…" | `cuantificar` | actividad, area_geografica, estrato |
| "Busco empresas **cerca de** [ubicación/coordenadas]" | `buscar` | condicion, coordenadas, distancia (máx 5000 m) |
| "Necesito **todas las [marca]**" (ej. OXXO, Walmart) | `nombre` | nombre, entidad (opcional), registro_inicial, registro_final |
| "Restaurantes / negocios **en [estado]**" | `buscarEntidad` | condicion, entidad, registro_inicial, registro_final |
| "Farmacias / negocios en **esta colonia/municipio** por **actividad**" | `buscarAreaAct` | entidad, municipio, sector/subsector/rama/clase, nombre, paginación |
| "Solo empresas de **X+ empleados**" (tamaño) | `buscarAreaActEstr` | igual que buscarAreaAct + **estrato** (0–7) |
| "Ya tengo el **ID**, quiero **detalles completos**" | `ficha` | id |

---

## Métodos en detalle

### 1. buscar
- **Uso:** Búsqueda general por **palabras clave** y/o **radio** (coordenadas + distancia en metros).
- **Parámetros obligatorios:** `condicion` (palabras, varias separadas por coma).
- **Opcionales:** `coordenadas` (lat,lon), `distancia` (máx **5000** m).
- **Cuándo:** Usuario no tiene códigos SCIAN; busca por tipo de negocio o dirección; prospección por cercanía.

### 2. ficha
- **Uso:** Detalle **completo** de **un** establecimiento por su ID.
- **Parámetros obligatorios:** `id` (clave única del establecimiento).
- **Cuándo:** Ya se obtuvo un ID con otro método; preparar visita comercial o validar datos.

### 3. nombre
- **Uso:** Búsqueda por **nombre comercial** o **razón social** (contiene).
- **Parámetros obligatorios:** `nombre`.
- **Opcionales:** `entidad` (2 dígitos; 00=todas), `registro_inicial`, `registro_final`.
- **Cuándo:** Franquicias, marcas, cadenas; encontrar todas las sucursales de una razón social.

### 4. buscarEntidad
- **Uso:** Búsqueda por **palabras clave** restringida a una **entidad federativa**.
- **Parámetros obligatorios:** `condicion`, `entidad` (01–32 o 00).
- **Opcionales:** `registro_inicial`, `registro_final`.
- **Cuándo:** Prospección por estado; campañas regionales.

### 5. buscarAreaAct
- **Uso:** Filtro por **ubicación geográfica** (entidad, municipio, localidad, AGEB, manzana) y **actividad económica** (SCIAN: sector, subsector, rama, clase).
- **Parámetros:** entidad (00=todo), municipio, localidad, ageb, manzana (0=omitir), sector, subsector, rama, clase, nombre (0=todos), registro_inicial, registro_final.
- **Cuándo:** Segmentación por industria y zona; no se requiere filtro por tamaño (estrato).

### 6. buscarAreaActEstr
- **Uso:** Igual que **buscarAreaAct** más filtro por **estrato** (tamaño por número de empleados).
- **Parámetros:** Los de buscarAreaAct + `estrato` (0–7).
- **Cuándo:** Prospección B2B por tamaño de empresa; solo empresas medianas/grandes, etc.

### 7. cuantificar
- **Uso:** Solo **conteos** (no listados). Análisis de mercado, viabilidad, comparación regional.
- **Parámetros:** `actividad` (SCIAN 2–6 dígitos o varias por coma), `area_geografica` (2–9 dígitos), `estrato` (0–7). "0" = no filtrar.
- **Cuándo:** "¿Cuántos hay?", estudios previos antes de búsquedas detalladas.

---

## Parámetros comunes

- **entidad:** Clave 2 dígitos (01–32) o **nombre/alias de estado** (ej. Jalisco, CDMX, Estado de México); la tool traduce. **00** = todo el país. Si no sabes la clave, escribe el nombre del estado o usa 00.
- **estrato (tamaño):** 0=todos, 1=0–5 pers, 2=6–10, 3=11–30, 4=31–50, 5=51–100, 6=101–250, 7=251+. También puedes enviar expresiones como **"micro"**, **"grande"**, **"pyme"** y la tool las traduce a 0–7.
- **Paginación:** `registro_inicial` y `registro_final` (ej. 1 y 50 para los primeros 50).
- **SCIAN:** sector (2), subsector (3), rama (4), clase (6 dígitos). Usar **"0"** para no filtrar; no inventes códigos.

### Catálogo de entidades federativas (claves 01–32)

La tool acepta **clave de 2 dígitos** o **nombre/alias** (ej. CDMX, Jalisco, Edo. Méx). Referencia breve: 01 Aguascalientes, 02 Baja California, 03 Baja California Sur, 04 Campeche, 05 Coahuila, 06 Colima, 07 Chiapas, 08 Chihuahua, **09 Ciudad de México (CDMX)**, 10 Durango, 11 Guanajuato, 12 Guerrero, 13 Hidalgo, **14 Jalisco**, **15 Estado de México**, 16 Michoacán, 17 Morelos, 18 Nayarit, 19 Nuevo León, 20 Oaxaca, 21 Puebla, 22 Querétaro, 23 Quintana Roo, 24 San Luis Potosí, 25 Sinaloa, 26 Sonora, 27 Tabasco, 28 Tamaulipas, 29 Tlaxcala, 30 Veracruz, 31 Yucatán, 32 Zacatecas.

### Búsqueda por ciudad o municipio

Cuando el usuario pida buscar en una **ciudad específica**, sigue esta estrategia:

1. **Opción rápida (recomendada):** Usa `method=buscarEntidad` con `condicion=[nombre de la ciudad o tipo de negocio]` y `entidad=[clave del estado]`. No necesitas saber la clave del municipio.
2. **Opción precisa (si necesitas filtrar por municipio):** Lee la skill **leads_mx_municipios** (`read_file` → `nanobot/skills/leads_mx_municipios/SKILL.md`) para obtener la clave de 3 dígitos del municipio. Luego usa `method=buscarAreaActEstr` con `entidad`, `municipio`, y los demás filtros.
3. **Si no encuentras la clave del municipio:** Usa `municipio=0` (todos los municipios del estado). **NUNCA inventes una clave.**

### Búsqueda por localidad, colonia o zona

Para búsquedas más específicas (localidad, colonia, AGEB), lee la skill **leads_mx_localidades** (`read_file` → `nanobot/skills/leads_mx_localidades/SKILL.md`). Regla general: usa `localidad=0`, `ageb=0`, `manzana=0` a menos que el usuario proporcione la clave numérica exacta.

## Restricciones importantes

- **Una entidad y un municipio por consulta** en buscarAreaAct/buscarAreaActEstr; para varios estados, una llamada por estado.
- **Distancia máxima 5000 m** en `buscar`.
- **Token obligatorio:** la tool solo funciona si está configurado `tools.leads_mx.token` en la configuración.

---

## Flujos recomendados

1. **Prospección B2B:** `cuantificar` → `buscarAreaActEstr` → `ficha` (para leads priorizados).
2. **Búsqueda por cercanía:** `buscar` (coordenadas + radio) → opcionalmente `ficha` para detalles.
3. **Por marca/franquicia:** `nombre` (por entidad si conviene) → `ficha` si se necesita detalle.
4. **Por estado y tipo:** `buscarEntidad` → luego refinar con `buscarAreaAct`/`buscarAreaActEstr` o `ficha`.

---

## Uso en conversación

1. **Analiza la intención:** ¿contar, listar, detalle por ID, por nombre/marca, por ciudad/estado, por tamaño?
2. **Elige el método** (tabla de criterios) y **escribe siempre `method`**.
3. **Para "buscar en [ciudad]":** Usa `buscarEntidad` con `condicion=[ciudad o tipo de negocio]` y `entidad=[clave del estado]`. Si necesitas la clave del municipio, lee la skill **leads_mx_municipios** con `read_file`.
4. **Nunca envíes cadenas vacías.** Para "no filtrar" usa `"0"` o `"00"`. Paginación por defecto: `registro_inicial=1`, `registro_final=50`.
5. **Nunca inventes** claves de municipio, localidad, AGEB ni SCIAN. Si no las tienes, usa `"0"` (omitir) o pregunta al usuario.
6. **Responde en el mismo idioma** que el usuario. Si falta algo crítico, pregunta o sugiere una alternativa.

## Errores frecuentes (evitar)

- Enviar **sin `method`** → siempre incluye `method`.
- Enviar **entidad=""** o **municipio=""** → usa `"00"` o `"0"` o la clave correcta.
- **Inventar claves de municipio** → si no sabes la clave, usa `municipio=0` o `method=buscarEntidad` con `condicion=[nombre de ciudad]`.
- **Inventar claves de localidad** → usa `localidad=0`. Consulta la skill **leads_mx_localidades** si necesitas guía.
- Repetir la misma llamada fallida → lee el mensaje de error de la tool: indica qué parámetro falta.
- Usar **buscarAreaActEstr** sin saber municipio → usa `municipio=0` o cambia a `buscarEntidad`.
docker compose build nanobot-cli && docker compose --profile cli run --rm -it nanobot-cli agent