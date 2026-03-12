---
name: leads_mx
description: Search establishments in Mexico via DENUE (INEGI) API. LeadsMx offers 7 methods (buscar, ficha, nombre, buscarEntidad, buscarAreaAct, buscarAreaActEstr, cuantificar). Always send method; use "0"/"00" instead of empty strings. Default pagination 25 records.
metadata: {"nanoiqqi":{"emoji":"📍","always":true,"requires":{"tools":["LeadsMx"]}}}
---

# LeadsMx – Establecimientos en México (DENUE)

Usa la tool **LeadsMx** cuando pidan negocios, establecimientos o empresas en México. Elige el **método** según la intención y adapta los parámetros a lo que el usuario pide; **nunca inventes** claves, coordenadas ni IDs.

**Referencia rápida de métodos:** contar → `cuantificar` | por coordenadas/radio → `buscar` | por marca → `nombre` | por estado + palabras → `buscarEntidad` | por zona + actividad (SCIAN) → `buscarAreaAct` | + tamaño (estrato) → `buscarAreaActEstr` | detalle por ID → `ficha`.

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
- **Valores por defecto razonables:** Si no especifica paginación, la tool usa `registro_inicial=1` y `registro_final=25` (véase construcción de endpoints más abajo). Si no especifica estado, usa `00` cuando el método lo permita. Si no especifica tamaño, usa `estrato=0`.
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

Cada método se mapea a un **endpoint** concreto de la API DENUE; el orden de los segmentos en la URL está en [Construcción de endpoints DENUE](#construcción-de-endpoints-denue-api-inegi).

### 1. buscar
- **Uso:** Búsqueda por **palabras clave** y/o **radio** (coordenadas + distancia en metros). **No tiene paginación** en la API.
- **Obligatorios:** `condicion`. **Opcionales:** `coordenadas` (lat,lon), `distancia` (máx 5000 m).
- **Cuándo:** Tipo de negocio en palabras; prospección por cercanía si hay lat/lon.

### 2. ficha
- **Uso:** Detalle de **un** establecimiento por ID.
- **Obligatorios:** `id`.
- **Cuándo:** Ya tienes un ID de una búsqueda anterior; validar datos o preparar visita.

### 3. nombre
- **Uso:** Búsqueda por **nombre comercial** o **razón social** (contiene). **Paginación:** registro_inicial, registro_final (por defecto 1–25).
- **Obligatorios:** `nombre`. **Opcionales:** `entidad`, `registro_inicial`, `registro_final`.
- **Cuándo:** Marcas, franquicias, cadenas; todas las sucursales de una razón social.

### 4. buscarEntidad
- **Uso:** Palabras clave en una **entidad federativa**. **Paginación:** por defecto 1–25.
- **Obligatorios:** `condicion`, `entidad`. **Opcionales:** `registro_inicial`, `registro_final`.
- **Cuándo:** "Restaurantes en Jalisco", "farmacias en CDMX"; prospección por estado.

### 5. buscarAreaAct
- **Uso:** **Ubicación** (entidad, municipio, localidad, AGEB, manzana) + **actividad SCIAN** (sector, subsector, rama, clase). **Paginación:** por defecto 1–25.
- **Parámetros:** entidad, municipio, localidad, ageb, manzana, sector, subsector, rama, clase, nombre (0=todos), registro_inicial, registro_final.
- **Cuándo:** Segmentación por industria y zona; sin filtro por tamaño.

### 6. buscarAreaActEstr
- **Uso:** Igual que **buscarAreaAct** + **estrato** (tamaño 0–7). **Paginación:** por defecto 1–25.
- **Parámetros:** Los de buscarAreaAct + `estrato`.
- **Cuándo:** Solo microempresas, solo medianas/grandes, etc.

### 7. cuantificar
- **Uso:** Solo **conteos** (no listados). No usa paginación.
- **Parámetros:** `actividad`, `area_geografica`, `estrato` ("0" = no filtrar).
- **Cuándo:** "¿Cuántos hay?", análisis previo antes de listar.

---

## Parámetros comunes

- **entidad:** Clave 2 dígitos (01–32) o **nombre/alias de estado** (Jalisco, CDMX, Estado de México, etc.); la tool traduce. **00** = todo el país.
- **estrato (tamaño):** 0=todos, 1=0–5 pers, 2=6–10, 3=11–30, 4=31–50, 5=51–100, 6=101–250, 7=251+. Puedes enviar **palabras** y la tool traduce (ver tabla abajo).
- **Paginación:** `registro_inicial` y `registro_final`. Por defecto la tool pide **25** registros (1–25). Para más: ej. `registro_inicial=1`, `registro_final=50`.
- **SCIAN:** sector (2 dígitos), subsector (3), rama (4), clase (6). Usa **"0"** para no filtrar. La tool acepta también **palabras** en sector/actividad (ver tabla).

### Palabras que la tool traduce automáticamente

**Estrato (tamaño):** `micro`, `pequeña`, `pyme`, `mediana`, `grande`, `0 a 5`, `6 a 10`, `11 a 30`, `31 a 50`, `51 a 100`, `101 a 250`, `251+` → se mapean a 0–7.

**Sector/actividad (SCIAN):** `restaurantes`, `farmacias`, `hoteles`, `comercio`, `retail`, `manufactura`, `industria`, `construcción`, `salud`, `educación`, `escuelas`, `servicios profesionales` → la tool traduce a código SCIAN (ej. restaurantes→72, farmacias→46). Si no hay coincidencia, usa `"0"` en esos campos y filtra por **condicion** en `buscar`/`buscarEntidad`.

### Catálogo de entidades federativas (claves 01–32)

La tool acepta **clave de 2 dígitos** o **nombre/alias** (ej. CDMX, Jalisco, Edo. Méx). Referencia breve: 01 Aguascalientes, 02 Baja California, 03 Baja California Sur, 04 Campeche, 05 Coahuila, 06 Colima, 07 Chiapas, 08 Chihuahua, **09 Ciudad de México (CDMX)**, 10 Durango, 11 Guanajuato, 12 Guerrero, 13 Hidalgo, **14 Jalisco**, **15 Estado de México**, 16 Michoacán, 17 Morelos, 18 Nayarit, 19 Nuevo León, 20 Oaxaca, 21 Puebla, 22 Querétaro, 23 Quintana Roo, 24 San Luis Potosí, 25 Sinaloa, 26 Sonora, 27 Tabasco, 28 Tamaulipas, 29 Tlaxcala, 30 Veracruz, 31 Yucatán, 32 Zacatecas.

### Búsqueda por ciudad o municipio

Cuando el usuario pida buscar en una **ciudad específica**, sigue esta estrategia:

1. **Opción rápida (recomendada):** Usa `method=buscarEntidad` con `condicion=[nombre de la ciudad o tipo de negocio]` y `entidad=[clave del estado]`. No necesitas saber la clave del municipio.
2. **Opción precisa (si necesitas filtrar por municipio):** Lee la skill **leads_mx_municipios** (`read_file` → `nanoiqqi/skills/leads_mx_municipios/SKILL.md`) para obtener la clave de 3 dígitos del municipio. Luego usa `method=buscarAreaActEstr` con `entidad`, `municipio`, y los demás filtros.
3. **Si no encuentras la clave del municipio:** Usa `municipio=0` (todos los municipios del estado). **NUNCA inventes una clave.**

### Búsqueda por localidad, colonia o zona

Para búsquedas más específicas (localidad, colonia, AGEB), lee la skill **leads_mx_localidades** (`read_file` → `nanoiqqi/skills/leads_mx_localidades/SKILL.md`). Regla general: usa `localidad=0`, `ageb=0`, `manzana=0` a menos que el usuario proporcione la clave numérica exacta.

## Restricciones importantes

- **Una entidad y un municipio por consulta** en buscarAreaAct/buscarAreaActEstr; para varios estados, una llamada por estado.
- **Distancia máxima 5000 m** en `buscar`.
- **Token obligatorio:** la tool solo funciona si está configurado `tools.leads_mx.token` en la configuración.
- **Paginación por defecto:** si no envías `registro_inicial`/`registro_final`, la tool pide 25 registros (1–25) en los métodos que lo soportan; para más, envíalos explícitamente.

---

## Flujos recomendados

1. **Prospección B2B:** `cuantificar` → `buscarAreaActEstr` → `ficha` (para leads priorizados).
2. **Búsqueda por cercanía:** `buscar` (coordenadas + radio) → opcionalmente `ficha` para detalles.
3. **Por marca/franquicia:** `nombre` (por entidad si conviene) → `ficha` si se necesita detalle.
4. **Por estado y tipo:** `buscarEntidad` → refinar con más paginación (`registro_final=50`) o `buscarAreaAct`/`ficha` si hace falta.
5. **Si el usuario pide "más resultados":** vuelve a llamar con el mismo método y `registro_inicial`/`registro_final` siguientes (ej. 26–50, 51–75).

## Ejemplos de parámetros (llamada a LeadsMx)

- **Restaurantes en Jalisco (primeros 25):**  
  `method=buscarEntidad`, `condicion=restaurante`, `entidad=14`  
  (registro_inicial/registro_final por defecto 1 y 25).

- **Farmacias en Estado de México, 50 resultados:**  
  `method=buscarEntidad`, `condicion=farmacia`, `entidad=15`, `registro_inicial=1`, `registro_final=50`.

- **Sucursales OXXO en todo el país:**  
  `method=nombre`, `nombre=OXXO`, `entidad=00`, `registro_inicial=1`, `registro_final=25` (o más si pide más).

- **Cuántos establecimientos en CDMX:**  
  `method=cuantificar`, `actividad=0`, `area_geografica=09`, `estrato=0`.

- **Microempresas (0–5 empleados) en un estado:**  
  `method=buscarAreaActEstr`, `entidad=14`, `municipio=0`, `sector=0`, `nombre=0`, `estrato=1`, `registro_inicial=1`, `registro_final=25`.

---

## Uso en conversación

1. **Analiza la intención:** ¿contar, listar, detalle por ID, por nombre/marca, por ciudad/estado, por tamaño?
2. **Elige el método** (tabla de criterios) y **escribe siempre `method`**.
3. **Para "buscar en [ciudad]":** Usa `buscarEntidad` con `condicion=[ciudad o tipo de negocio]` y `entidad=[clave del estado]`. Si necesitas la clave del municipio, lee la skill **leads_mx_municipios** con `read_file`.
4. **Nunca envíes cadenas vacías.** Para "no filtrar" usa `"0"` o `"00"`. Paginación por defecto: `registro_inicial=1`, `registro_final=25` (construcción del endpoint DENUE).
5. **Nunca inventes** claves de municipio, localidad, AGEB ni SCIAN. Si no las tienes, usa `"0"` (omitir) o pregunta al usuario.
6. **Responde en el mismo idioma** que el usuario. Si falta algo crítico, pregunta o sugiere una alternativa.

## Errores frecuentes (evitar)

- Enviar **sin `method`** → la tool falla; siempre incluye `method`.
- Enviar **entidad=""** o **municipio=""** → usa `"00"` o `"0"` o la clave correcta; nunca cadenas vacías.
- **Inventar claves** de municipio, localidad, AGEB o SCIAN → usa `0`/`00` o consulta las skills leads_mx_municipios / leads_mx_localidades; si no sabes municipio, `buscarEntidad` con condicion=ciudad.
- **Método equivocado:** usar `buscar` para "en Jalisco" (no hay filtro entidad) → usa `buscarEntidad`. Usar `cuantificar` cuando piden listado → usa `buscarEntidad` o `buscarAreaAct`/`buscarAreaActEstr`.
- Repetir la misma llamada fallida → el mensaje de error indica qué parámetro falta o está mal.

---

## Construcción de endpoints DENUE (API INEGI) {#construcción-de-endpoints-denue-api-inegi}

La tool construye la URL así: **base** + **método** + **segmentos en orden** + **token**. El token va siempre al final; las cadenas vacías se sustituyen por `0` o `00`.

**Base:** `https://www.inegi.org.mx/app/api/denue/v1/consulta`  
**Formato:** `{base}/{Metodo}/{seg1}/{seg2}/.../{token}`

### Tabla rápida de endpoints

| Método | Patrón de path (sin base ni token) | ¿Paginación? | Default reg_final |
|--------|------------------------------------|--------------|-------------------|
| Buscar | `Buscar/condicion/coordenadas/distancia` | No | — |
| Ficha | `Ficha/id` | No | — |
| Nombre | `Nombre/nombre/entidad/reg_ini/reg_fin` | Sí | 25 |
| BuscarEntidad | `BuscarEntidad/condicion/entidad/reg_ini/reg_fin` | Sí | 25 |
| BuscarAreaAct | `BuscarAreaAct/entidad/municipio/localidad/ageb/manzana/sector/subsector/rama/clase/nombre/reg_ini/reg_fin/id_param` | Sí | 25 |
| BuscarAreaActEstr | Como BuscarAreaAct + `estrato` antes del token | Sí | 25 |
| Cuantificar | `Cuantificar/actividad/area_geografica/estrato` | No | — |

**Ejemplo de URL completa (BuscarEntidad):**  
`https://www.inegi.org.mx/app/api/denue/v1/consulta/BuscarEntidad/restaurante/14/1/25/{token}`  
→ restaurantes en Jalisco (entidad 14), registros 1 a 25.

### 1. Buscar

```
/Buscar/{condicion}/{coordenadas}/{distancia}/{token}
```

- **condicion:** Palabras clave (obligatorio).
- **coordenadas:** `lat,lon` sin espacios, o `0` para no filtrar por ubicación.
- **distancia:** Metros (1–5000), o `0` si no hay coordenadas.

*No usa paginación en la API; INEGI devuelve todos los resultados que coincidan.*

### 2. Ficha

```
/Ficha/{id}/{token}
```

- **id:** Clave única del establecimiento (obligatorio).

### 3. Nombre

```
/Nombre/{nombre}/{entidad}/{registro_inicial}/{registro_final}/{token}
```

- **nombre:** Nombre o razón social a buscar (obligatorio).
- **entidad:** `00` = todo el país, `01`–`32` = clave del estado.
- **registro_inicial:** Desde qué registro (1-based). Por defecto en la tool: `1`.
- **registro_final:** Hasta qué registro. Por defecto en la tool: `25` (paginación por defecto).

### 4. BuscarEntidad

```
/BuscarEntidad/{condicion}/{entidad}/{registro_inicial}/{registro_final}/{token}
```

- **condicion:** Palabras clave (obligatorio).
- **entidad:** `00` o clave 2 dígitos del estado.
- **registro_inicial** / **registro_final:** Paginación. Por defecto: `1` y `25`.

### 5. BuscarAreaAct

```
/BuscarAreaAct/{entidad}/{municipio}/{localidad}/{ageb}/{manzana}/{sector}/{subsector}/{rama}/{clase}/{nombre}/{registro_inicial}/{registro_final}/{id_param}/{token}
```

- **entidad:** `00` o `01`–`32`.
- **municipio:** 3 dígitos, `0` = todos.
- **localidad:** 4 dígitos, `0` = todas.
- **ageb:** 4 dígitos, `0` = omitir.
- **manzana:** 3 dígitos, `0` = omitir.
- **sector / subsector / rama / clase:** Códigos SCIAN; `0` = no filtrar.
- **nombre:** Nombre del establecimiento o `0`.
- **registro_inicial** / **registro_final:** Por defecto `1` y `25`.
- **id_param:** En la tool se envía `0`.

### 6. BuscarAreaActEstr

Misma estructura que **BuscarAreaAct**, con **estrato** antes del token:

```
/BuscarAreaActEstr/{entidad}/{municipio}/{localidad}/{ageb}/{manzana}/{sector}/{subsector}/{rama}/{clase}/{nombre}/{registro_inicial}/{registro_final}/{id_param}/{estrato}/{token}
```

- **estrato:** 0–7 (0=todos, 1=0–5 empleados, …, 7=251+).

### 7. Cuantificar

```
/Cuantificar/{actividad}/{area_geografica}/{estrato}/{token}
```

- **actividad:** Clave(s) SCIAN 2–6 dígitos, o `0`.
- **area_geografica:** Código(s) de área 2–9 dígitos, o `0` (todo el país).
- **estrato:** 0–7.

---

**Resumen:** Solo **Nombre**, **BuscarEntidad**, **BuscarAreaAct** y **BuscarAreaActEstr** aceptan paginación en la URL (`registro_inicial`, `registro_final`). Por defecto la tool usa `1` y `25`; para más resultados, envía explícitamente `registro_final` (ej. 50 o 100). **Buscar**, **Ficha** y **Cuantificar** no usan paginación.