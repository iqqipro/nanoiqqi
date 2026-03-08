"""LeadsMx tool: búsqueda de establecimientos en México vía API DENUE (INEGI).

Soporta todos los métodos de la API DENUE v1:
- buscar: búsqueda general por palabras clave y/o radio (coordenadas + distancia).
- ficha: detalle completo de un establecimiento por ID.
- nombre: búsqueda por nombre o razón social.
- buscarEntidad: búsqueda por palabras clave filtrada por entidad federativa.
- buscarAreaAct: ubicación geográfica + actividad económica (SCIAN), sin estrato.
- buscarAreaActEstr: igual que buscarAreaAct más filtro por estrato (tamaño).
- cuantificar: solo conteos por actividad, área geográfica y estrato.
"""

from __future__ import annotations

import time
import unicodedata
from typing import Any

import httpx

from nanobot.agent.tools.base import Tool

DENUE_BASE = "https://www.inegi.org.mx/app/api/denue/v1/consulta"

# Métodos disponibles (nombre en API INEGI).
DENUE_METHODS = (
    "Buscar",
    "Ficha",
    "Nombre",
    "BuscarEntidad",
    "BuscarAreaAct",
    "BuscarAreaActEstr",
    "Cuantificar",
)

# Índices de campos en respuesta DENUE (listas por establecimiento).
DENUE_CAMPO_ID = 1
DENUE_CAMPO_NOMBRE = 2
DENUE_CAMPO_RAZON_SOCIAL = 3
DENUE_CAMPO_CLASE_ACTIVIDAD = 4
DENUE_CAMPO_ESTRATO = 5
DENUE_CAMPO_TIPO_VIALIDAD = 6
DENUE_CAMPO_CALLE = 7
DENUE_CAMPO_NUM_EXTERIOR = 8
DENUE_CAMPO_NUM_INTERIOR = 9
DENUE_CAMPO_COLONIA = 10
DENUE_CAMPO_CP = 11
DENUE_CAMPO_LOCALIDAD_MUN_ENT = 12
DENUE_CAMPO_TELEFONO = 13
DENUE_CAMPO_CORREO = 14
DENUE_CAMPO_SITIO_INTERNET = 15
DENUE_CAMPO_FECHA_ALTA = 32

# Distancia máxima en metros (límite API).
DENUE_DISTANCIA_MAX_METROS = 5000

# TTL del caché en memoria (segundos): 24 horas.
DENUE_CACHE_TTL_SECONDS = 24 * 3600

# Máximo de caracteres en respuesta formateada antes de truncar (opcional).
DENUE_OUTPUT_MAX_CHARS = 4000

# Número de filas a mostrar en listados (reducir tokens).
DENUE_SHOW_ROWS = 12


def _normalize_lookup(s: str) -> str:
    """Normaliza para búsqueda en mapas: minúsculas y sin acentos."""
    if not s or not str(s).strip():
        return ""
    t = unicodedata.normalize("NFD", str(s).strip().lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# Entidades federativas: nombres y alias (normalizados) → clave 2 dígitos (01-32).
ENTIDADES_MAP: dict[str, str] = {}
for _k, _names in (
    ("01", ("aguascalientes", "ags")),
    ("02", ("baja california", "bc", "baja california norte")),
    ("03", ("baja california sur", "bcs")),
    ("04", ("campeche", "camp")),
    ("05", ("coahuila", "coah", "coahuila de zaragoza")),
    ("06", ("colima", "col")),
    ("07", ("chiapas", "chis")),
    ("08", ("chihuahua", "chih")),
    ("09", ("ciudad de mexico", "cdmx", "df", "distrito federal", "cd mx", "ciudad de méxico")),
    ("10", ("durango", "dgo")),
    ("11", ("guanajuato", "gto", "guan")),
    ("12", ("guerrero", "gro", "gue")),
    ("13", ("hidalgo", "hgo", "hid")),
    ("14", ("jalisco", "jal", "guadalajara")),
    ("15", ("estado de mexico", "edomex", "mexico", "edo mex", "estado de méxico", "méxico")),
    ("16", ("michoacan", "michoacán", "mich", "michoacan de ocampo")),
    ("17", ("morelos", "mor")),
    ("18", ("nayarit", "nay")),
    ("19", ("nuevo leon", "nuevo león", "nl", "nuevo leon")),
    ("20", ("oaxaca", "oax")),
    ("21", ("puebla", "pue")),
    ("22", ("queretaro", "querétaro", "qro", "queretaro de arteaga")),
    ("23", ("quintana roo", "q roo", "quintana roo")),
    ("24", ("san luis potosi", "san luis potosí", "slp")),
    ("25", ("sinaloa", "sin")),
    ("26", ("sonora", "son")),
    ("27", ("tabasco", "tab")),
    ("28", ("tamaulipas", "tamps", "tam")),
    ("29", ("tlaxcala", "tlax")),
    ("30", ("veracruz", "ver", "veracruz de ignacio de la llave")),
    ("31", ("yucatan", "yucatán", "yuc")),
    ("32", ("zacatecas", "zac")),
):
    for _n in _names:
        ENTIDADES_MAP[_normalize_lookup(_n)] = _k

# Estrato (tamaño de empresa): expresiones → valor 0-7. 0 = todos.
# 1=0-5, 2=6-10, 3=11-30, 4=31-50, 5=51-100, 6=101-250, 7=251+
ESTRATO_MAP: dict[str, int] = {
    "todos": 0, "cualquiera": 0, "sin filtro": 0, "todas": 0, "cualesquiera": 0,
    "micro": 1, "microempresa": 1, "0 a 5": 1, "chico": 1, "chica": 1, "mini": 1,
    "pequeña": 2, "pequeño": 2, "pyme": 2, "6 a 10": 2, "6-10": 2,
    "mediana": 4, "mediano": 4, "31 a 50": 4, "31-50": 4,
    "grande": 7, "grandes": 7, "251+": 7, "251 o mas": 7, "mas de 250": 7,
    "51 a 100": 5, "51-100": 5, "101 a 250": 6, "101-250": 6,
    "11 a 30": 3, "11-30": 3,
}

# SCIAN (opcional): términos comunes → sector 2 dígitos o rama 4 dígitos.
# Solo para reducir errores cuando el LLM envía palabra en lugar de código.
SCIAN_MAP: dict[str, str] = {
    "restaurantes": "72", "restaurante": "72",
    "farmacias": "46", "farmacia": "46",
    "hoteles": "72", "hotel": "72", "hospedaje": "72",
    "comercio": "43", "comercio al por menor": "46", "retail": "46",
    "manufactura": "31", "industria": "31",
    "construccion": "23", "construcción": "23",
    "salud": "62", "servicios de salud": "62",
    "educacion": "61", "educación": "61", "escuelas": "61",
    "servicios profesionales": "54", "profesionales": "54",
}


def _str_param(v: Any, default: str = "0") -> str:
    """Normaliza valor a string; None o cadena vacía/espacios → default. NUNCA devuelve ''."""
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _normalize_geo(s: str) -> str:
    """Para entidad: '' → '00'. Para municipio/localidad/ageb/manzana/sector/etc: '' → '0'."""
    if s is None or not str(s).strip():
        return "0"
    t = str(s).strip()
    return t if t else "0"


def _resolve_entidad(value: Any) -> str:
    """
    Resuelve entidad federativa: vacío/'0'/'00' → '00'.
    Si ya son 2 dígitos válidos (01-32), los devuelve con cero a la izquierda.
    Si no, busca en ENTIDADES_MAP por nombre/alias normalizado y devuelve la clave o '00'.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return "00"
    s = str(value).strip()
    if s in ("0", "00"):
        return "00"
    if len(s) <= 2 and s.isdigit():
        n = int(s)
        if 1 <= n <= 32:
            return f"{n:02d}"
        return "00"
    key = _normalize_lookup(s)
    return ENTIDADES_MAP.get(key, "00")


def _resolve_estrato(value: Any) -> int:
    """
    Resuelve estrato (tamaño): 0-7. Si ya es entero válido, lo devuelve.
    Si es string, busca en ESTRATO_MAP (normalizado) y devuelve el valor; sin match → 0.
    """
    if value is None:
        return 0
    if isinstance(value, int) and 0 <= value <= 7:
        return value
    try:
        n = int(value)
        if 0 <= n <= 7:
            return n
    except (TypeError, ValueError):
        pass
    key = _normalize_lookup(str(value).strip())
    return ESTRATO_MAP.get(key, 0)


def _resolve_scian(keywords: str) -> str:
    """
    Resuelve término común a código SCIAN (sector 2 dígitos). Sin match → '0'.
    Útil cuando el LLM envía 'restaurantes' en lugar de sector '72'.
    """
    if not keywords or not str(keywords).strip():
        return "0"
    s = str(keywords).strip()
    if s == "0" or s.isdigit():
        return s
    key = _normalize_lookup(s)
    return SCIAN_MAP.get(key, "0")


def _int_param(v: Any, default: int = 0) -> str:
    if v is None:
        return str(default)
    try:
        return str(int(v))
    except (TypeError, ValueError):
        return str(default)


def _get_campo(row: list[Any] | dict[str, Any], index: int, key_aliases: tuple[str, ...]) -> str:
    """Obtiene el valor del campo por índice (lista) o por clave (dict)."""
    if isinstance(row, list):
        if 0 <= index < len(row) and row[index] is not None:
            return str(row[index]).strip()
        return ""
    if isinstance(row, dict):
        for k in key_aliases:
            if k in row and row[k] is not None:
                return str(row[k]).strip()
    return ""


def _cell(s: str, max_len: int = 50) -> str:
    """Escapa pipes y acorta celdas para tabla markdown legible."""
    if not s or not s.strip():
        return "—"
    s = str(s).strip().replace("|", "\\|").replace("\n", " ")
    return (s[: max_len - 3] + "…") if len(s) > max_len else s


def _format_denue_results(items: list[Any], method: str = "") -> str:
    """
    Formatea la lista de establecimientos DENUE como tabla markdown con emojis.
    Acepta listas de listas (orden INEGI) o listas de diccionarios.
    Muestra como máximo DENUE_SHOW_ROWS filas para reducir tokens.
    """
    if not items:
        return "📭 **Sin resultados** para los filtros indicados."

    total = len(items)
    show = items[:DENUE_SHOW_ROWS]
    header_emoji = "📋"
    title = f"{header_emoji} **{total} establecimiento(s) encontrado(s)**"
    if method:
        title += f" _(método: {method})_"
    title += "\n"

    # Cabecera de tabla con emojis
    col_headers = ["#", "🏢 Nombre", "📄 Razón social", "📞 Teléfono", "✉️ Correo", "🌐 Web", "📍 Dirección"]
    sep = "| " + " | ".join(["---"] * len(col_headers)) + " |"
    table_lines = ["| " + " | ".join(col_headers) + " |", sep]

    for i, row in enumerate(show, 1):
        if not isinstance(row, (list, dict)):
            table_lines.append(f"| {i} | {_cell(str(row))} | — | — | — | — | — |")
            continue
        nombre = _get_campo(row, DENUE_CAMPO_NOMBRE, ("Nombre", "nombre", "Nombre del establecimiento"))
        razon = _get_campo(row, DENUE_CAMPO_RAZON_SOCIAL, ("Razon_social", "Razón social", "razon_social"))
        tel = _get_campo(row, DENUE_CAMPO_TELEFONO, ("Telefono", "Teléfono", "telefono"))
        correo = _get_campo(row, DENUE_CAMPO_CORREO, ("Correo_electronico", "Correo electrónico", "correo"))
        sitio = _get_campo(row, DENUE_CAMPO_SITIO_INTERNET, ("Sitio_internet", "Página de internet", "sitio_internet"))
        tipo_vial = _get_campo(row, DENUE_CAMPO_TIPO_VIALIDAD, ("Tipo_vialidad", "Tipo de la vialidad"))
        calle = _get_campo(row, DENUE_CAMPO_CALLE, ("Calle", "calle"))
        num_ext = _get_campo(row, DENUE_CAMPO_NUM_EXTERIOR, ("Num_exterior", "Número exterior"))
        num_int = _get_campo(row, DENUE_CAMPO_NUM_INTERIOR, ("Num_interior", "Número interior"))
        col = _get_campo(row, DENUE_CAMPO_COLONIA, ("Colonia", "colonia"))
        cp = _get_campo(row, DENUE_CAMPO_CP, ("CP", "Codigo_postal", "Código postal"))
        loc_mun = _get_campo(row, DENUE_CAMPO_LOCALIDAD_MUN_ENT, ("Localidad_municipio_entidad", "Localidad, municipio y entidad federativa"))
        dir_parts = [p for p in [tipo_vial, calle, num_ext, num_int, col, cp, loc_mun] if p]
        direccion = ", ".join(dir_parts) if dir_parts else ""

        table_lines.append(
            "| " + " | ".join([
                str(i),
                _cell(nombre or razon or "—"),
                _cell(razon if razon != (nombre or "") else "—"),
                _cell(tel),
                _cell(correo),
                _cell(sitio),
                _cell(direccion, 60),
            ]) + " |"
        )

    out = title + "\n" + "\n".join(table_lines)
    if total > DENUE_SHOW_ROWS:
        out += f"\n\n📄 _Mostrando {DENUE_SHOW_ROWS} de {total}. Usa_ `registro_inicial` _y_ `registro_final` _para ver más._"
    if len(out) > DENUE_OUTPUT_MAX_CHARS:
        out = out[:DENUE_OUTPUT_MAX_CHARS] + f"\n\n📄 _[Respuesta truncada. Total: {total} establecimientos.]_"
    return out


def _format_ficha(row: list[Any] | dict[str, Any]) -> str:
    """Formatea un único establecimiento (respuesta de Ficha) con emojis y bloques legibles."""
    if not isinstance(row, (list, dict)):
        return str(row)
    nombre = _get_campo(row, DENUE_CAMPO_NOMBRE, ("Nombre", "nombre"))
    razon = _get_campo(row, DENUE_CAMPO_RAZON_SOCIAL, ("Razon_social", "Razón social", "razon_social"))
    id_est = _get_campo(row, DENUE_CAMPO_ID, ("Id", "id"))
    tel = _get_campo(row, DENUE_CAMPO_TELEFONO, ("Telefono", "Teléfono"))
    correo = _get_campo(row, DENUE_CAMPO_CORREO, ("Correo_electronico", "Correo electrónico"))
    sitio = _get_campo(row, DENUE_CAMPO_SITIO_INTERNET, ("Sitio_internet", "Página de internet"))
    tipo_vial = _get_campo(row, DENUE_CAMPO_TIPO_VIALIDAD, ("Tipo_vialidad",))
    calle = _get_campo(row, DENUE_CAMPO_CALLE, ("Calle", "calle"))
    num_ext = _get_campo(row, DENUE_CAMPO_NUM_EXTERIOR, ("Num_exterior",))
    num_int = _get_campo(row, DENUE_CAMPO_NUM_INTERIOR, ("Num_interior",))
    col = _get_campo(row, DENUE_CAMPO_COLONIA, ("Colonia",))
    cp = _get_campo(row, DENUE_CAMPO_CP, ("CP", "Codigo_postal"))
    loc_mun = _get_campo(row, DENUE_CAMPO_LOCALIDAD_MUN_ENT, ("Localidad_municipio_entidad",))
    fecha_alta = _get_campo(row, DENUE_CAMPO_FECHA_ALTA, ("Fecha_alta",))
    clase = _get_campo(row, DENUE_CAMPO_CLASE_ACTIVIDAD, ("Clase_actividad", "Clase de actividad"))
    estrato = _get_campo(row, DENUE_CAMPO_ESTRATO, ("Estrato", "estrato"))
    dir_full = ", ".join(filter(None, [tipo_vial, calle, num_ext, num_int, col, cp, loc_mun])) or "—"

    lines = [
        "🏢 **" + (nombre or razon or "Establecimiento") + "**",
        "",
        "| Campo | Valor |",
        "|-------|-------|",
        f"| 🆔 ID | {id_est or '—'} |",
        f"| 📄 Razón social | {razon or '—'} |",
        f"| 📂 Actividad (clase) | {clase or '—'} |",
        f"| 👥 Estrato (tamaño) | {estrato or '—'} |",
        f"| 📍 Dirección | {dir_full} |",
        f"| 📞 Teléfono | {tel or '—'} |",
        f"| ✉️ Correo | {correo or '—'} |",
        f"| 🌐 Sitio web | {sitio or '—'} |",
        f"| 📅 Fecha de alta | {fecha_alta or '—'} |",
    ]
    return "\n".join(lines)


def _format_cuantificar(data: Any) -> str:
    """Formatea la respuesta de Cuantificar (conteos) con emojis y formato claro."""
    if isinstance(data, dict):
        total = data.get("total_establecimientos", data.get("total", data.get("Total", "")))
        if total != "":
            filtros = data.get("filtros_aplicados", data)
            return (
                "📊 **Conteo DENUE**\n\n"
                "| Concepto | Valor |\n|----------|-------|\n"
                f"| 🏢 Total de establecimientos | **{total}** |\n\n"
                "_Filtros aplicados:_ " + str(filtros)
            )
        return str(data)
    if isinstance(data, list) and len(data) > 0:
        n = data[0] if len(data) == 1 else data
        return (
            "📊 **Conteo DENUE**\n\n"
            "| Concepto | Valor |\n|----------|-------|\n"
            f"| 🏢 Total de establecimientos | **{n}** |"
        )
    return str(data)


class LeadsMx(Tool):
    """
    Herramienta para buscar prospectos/establecimientos en México con la API DENUE (INEGI).
    Soporta 7 métodos: buscar, ficha, nombre, buscarEntidad, buscarAreaAct, buscarAreaActEstr, cuantificar.
    Elige el método según la intención: contar (cuantificar), búsqueda por radio (buscar),
    por nombre/marca (nombre), por estado (buscarEntidad), por actividad/ubicación (buscarAreaAct/buscarAreaActEstr),
    o detalle por ID (ficha).
    """

    name = "LeadsMx"
    description = (
        "Busca prospectos/establecimientos en México con la API DENUE (INEGI). "
        "OBLIGATORIO: Siempre envía 'method'. "
        "NUNCA envíes cadenas vacías: usa '00' (entidad=todo el país), '0' (municipio/localidad/sector/etc=omitir). "
        "Para 'buscar en [ciudad]': usa method=buscarEntidad con condicion=[ciudad o tipo de negocio] y entidad=[clave del estado]. "
        "Si necesitas clave de municipio: consulta skill leads_mx_municipios (read_file nanobot/skills/leads_mx_municipios/SKILL.md). NUNCA inventes claves. "
        "Si no sabes la clave de municipio, usa municipio=0 (todos). "
        "Métodos: buscar, ficha, nombre, buscarEntidad, buscarAreaAct, buscarAreaActEstr, cuantificar. "
        "Paginación: registro_inicial, registro_final. Entidad 2 dígitos; 00=todo. Distancia máx 5000 m."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["buscar", "ficha", "nombre", "buscarEntidad", "buscarAreaAct", "buscarAreaActEstr", "cuantificar"],
                "description": (
                    "Método DENUE a usar: buscar=búsqueda por palabras y/o radio; ficha=detalle por ID; "
                    "nombre=por nombre/razón social; buscarEntidad=por estado+palabras; "
                    "buscarAreaAct=ubicación+actividad SCIAN; buscarAreaActEstr=+estrato; cuantificar=solo conteos."
                ),
            },
            # --- Buscar
            "condicion": {
                "type": "string",
                "description": "Palabras clave para buscar (buscar, buscarEntidad). Varias separadas por coma. Ej: restaurante, farmacia.",
            },
            "coordenadas": {
                "type": "string",
                "description": "Latitud,longitud sin espacios (solo para method=buscar). Ej: 19.4326,-99.1332.",
            },
            "distancia": {
                "type": "integer",
                "description": "Radio en metros (solo para method=buscar, máx 5000).",
                "minimum": 1,
                "maximum": 5000,
            },
            # --- Ficha
            "id": {
                "type": "string",
                "description": "ID del establecimiento (solo para method=ficha).",
            },
            # --- Nombre / BuscarEntidad
            "nombre": {
                "type": "string",
                "description": "Nombre o razón social a buscar (method=nombre o en buscarAreaAct/buscarAreaActEstr; use '0' para todos, nunca vacío).",
            },
            "nombre_establecimiento": {
                "type": "string",
                "description": "Alias de 'nombre' para buscarAreaAct/buscarAreaActEstr. Use '0' para todos. No enviar vacío.",
            },
            "entidad": {
                "type": "string",
                "description": "Entidad: clave 2 dígitos (01-32) o nombre/alias de estado (ej. Jalisco, CDMX, Estado de México). La tool traduce a clave. Use '00' para todo el país.",
            },
            "registro_inicial": {
                "type": "integer",
                "description": "Registro inicial para paginación (1-based).",
                "minimum": 1,
            },
            "registro_final": {
                "type": "integer",
                "description": "Registro final para paginación.",
                "minimum": 1,
            },
            # --- BuscarAreaAct / BuscarAreaActEstr
            "municipio": {"type": "string", "description": "Municipio 3 dígitos. 0=todos.", "maxLength": 3},
            "localidad": {"type": "string", "description": "Localidad 4 dígitos. 0=todas.", "maxLength": 4},
            "ageb": {"type": "string", "description": "AGEB 4 dígitos. 0=omitir.", "maxLength": 4},
            "manzana": {"type": "string", "description": "Manzana 3 dígitos. 0=omitir.", "maxLength": 4},
            "sector": {"type": "string", "description": "Sector SCIAN 2 dígitos. 0=todos."},
            "subsector": {"type": "string", "description": "Subsector 3 dígitos. 0=omitir."},
            "rama": {"type": "string", "description": "Rama 4 dígitos. 0=omitir."},
            "clase": {"type": "string", "description": "Clase 6 dígitos. 0=omitir."},
            "estrato": {
                "type": "integer",
                "description": "Tamaño: 0-7 (0=todos, 1=0-5, 2=6-10, 3=11-30, 4=31-50, 5=51-100, 6=101-250, 7=251+) o expresiones como 'micro', 'grande', 'pyme'; la tool traduce.",
                "minimum": 0,
                "maximum": 7,
            },
            # --- Cuantificar
            "actividad": {
                "type": "string",
                "description": "Clave SCIAN 2-6 dígitos o varias separadas por coma (method=cuantificar). 0=todas.",
            },
            "area_geografica": {
                "type": "string",
                "description": "Área geográfica 2-9 dígitos o varias por coma (method=cuantificar). 0=todo el país.",
            },
        },
        "required": ["method"],
    }

    def __init__(self, token: str = ""):
        self.token = (token or "").strip()
        # Caché en memoria: clave (URL) → { "data": respuesta cruda, "expires": timestamp }
        self._cache: dict[str, dict[str, Any]] = {}

    def _url_buscar(self, condicion: str, coordenadas: str, distancia: str) -> str:
        # API: Buscar/condicion/coordenadas/distancia/token (0 para omitir coordenadas/distancia)
        segs = [condicion, coordenadas or "0", distancia or "0", self.token]
        return f"{DENUE_BASE}/Buscar/{'/'.join(segs)}"

    def _url_ficha(self, id_est: str) -> str:
        return f"{DENUE_BASE}/Ficha/{id_est}/{self.token}"

    def _url_nombre(self, nombre: str, entidad: str, reg_ini: str, reg_fin: str) -> str:
        return f"{DENUE_BASE}/Nombre/{nombre}/{entidad}/{reg_ini}/{reg_fin}/{self.token}"

    def _url_buscar_entidad(self, condicion: str, entidad: str, reg_ini: str, reg_fin: str) -> str:
        return f"{DENUE_BASE}/BuscarEntidad/{condicion}/{entidad}/{reg_ini}/{reg_fin}/{self.token}"

    def _url_buscar_area_act(
        self,
        entidad: str,
        municipio: str,
        localidad: str,
        ageb: str,
        manzana: str,
        sector: str,
        subsector: str,
        rama: str,
        clase: str,
        nombre: str,
        reg_ini: str,
        reg_fin: str,
        id_param: str,
        estrato: str | None = None,
    ) -> str:
        segs = [
            entidad, municipio, localidad, ageb, manzana,
            sector, subsector, rama, clase, nombre,
            reg_ini, reg_fin, id_param,
        ]
        if estrato is not None:
            segs.append(estrato)
        segs.append(self.token)
        method = "BuscarAreaActEstr" if estrato is not None else "BuscarAreaAct"
        return f"{DENUE_BASE}/{method}/{'/'.join(segs)}"

    def _url_cuantificar(self, actividad: str, area_geografica: str, estrato: str) -> str:
        return f"{DENUE_BASE}/Cuantificar/{actividad}/{area_geografica}/{estrato}/{self.token}"

    def _hint_methods(self) -> str:
        """Mensaje corto para guiar al modelo cuando falta method o hay error de parámetros."""
        return (
            "Guía: "
            "buscar en [ciudad] → method=buscarEntidad, condicion=[ciudad o tipo], entidad=[clave estado, ej 15 para Edo.Méx]. "
            "Listar por municipio → method=buscarAreaActEstr, entidad=[clave], municipio=[clave 3 dígitos o 0 para todos]. "
            "Si no sabes la clave del municipio, usa municipio=0 o consulta skill leads_mx_municipios. "
            "Siempre envía 'method'. Nunca envíes cadenas vacías: usa '0' o '00'."
        )

    async def execute(self, **kwargs: Any) -> str:
        if not self.token:
            return (
                "Error: Token de API DENUE no configurado. "
                "Configure tools.leads_mx.token en ~/.nanobot/config.json para usar esta herramienta."
            )

        # Compatibilidad: alias nombre_establecimiento → nombre (schema legacy)
        if "nombre_establecimiento" in kwargs and "nombre" not in kwargs:
            kwargs = {**kwargs, "nombre": kwargs.get("nombre_establecimiento")}

        method = (kwargs.get("method") or "").strip().lower()

        # Inferir method si falta: si hay parámetros de área/geografía, asumir buscarAreaActEstr
        if not method:
            if any(
                kwargs.get(k) not in (None, "", [])
                for k in ("entidad", "municipio", "registro_inicial", "registro_final", "nombre", "nombre_establecimiento")
            ):
                method = "buscarareaactestr"
            else:
                return (
                    "Error: Falta el parámetro obligatorio 'method'. "
                    + self._hint_methods()
                )

        if method not in (
            "buscar",
            "ficha",
            "nombre",
            "buscarentidad",
            "buscarareaact",
            "buscarareaactestr",
            "cuantificar",
        ):
            return (
                "Error: 'method' debe ser uno de: buscar, ficha, nombre, buscarEntidad, "
                "buscarAreaAct, buscarAreaActEstr, cuantificar. "
                + self._hint_methods()
            )

        url: str | None = None

        if method == "buscar":
            condicion = _str_param(kwargs.get("condicion"))
            if not condicion or condicion == "0":
                return "Error: method=buscar requiere 'condicion' (palabras clave). " + self._hint_methods()
            coordenadas = _str_param(kwargs.get("coordenadas"), "")
            distancia = _int_param(kwargs.get("distancia"), 0)
            if coordenadas and coordenadas != "0" and int(distancia or 0) > DENUE_DISTANCIA_MAX_METROS:
                return f"Error: distancia no puede superar {DENUE_DISTANCIA_MAX_METROS} m. " + self._hint_methods()
            url = self._url_buscar(condicion, coordenadas or "0", distancia or "0")

        elif method == "ficha":
            id_est = _str_param(kwargs.get("id"))
            if not id_est or id_est == "0":
                return "Error: method=ficha requiere 'id' (clave del establecimiento). " + self._hint_methods()
            url = self._url_ficha(id_est)

        elif method == "nombre":
            nombre = _str_param(kwargs.get("nombre"))
            if not nombre or nombre == "0":
                return "Error: method=nombre requiere 'nombre'. " + self._hint_methods()
            entidad = _resolve_entidad(kwargs.get("entidad"))
            reg_ini = _int_param(kwargs.get("registro_inicial"), 1)
            reg_fin = _int_param(kwargs.get("registro_final"), 100)
            url = self._url_nombre(nombre, entidad, reg_ini, reg_fin)

        elif method == "buscarentidad":
            condicion = _str_param(kwargs.get("condicion"))
            if not condicion or condicion == "0":
                return "Error: method=buscarEntidad requiere 'condicion'. Para 'buscar en Toluca' usa condicion=toluca, entidad=15. " + self._hint_methods()
            entidad = _resolve_entidad(kwargs.get("entidad"))
            reg_ini = _int_param(kwargs.get("registro_inicial"), 1)
            reg_fin = _int_param(kwargs.get("registro_final"), 100)
            url = self._url_buscar_entidad(condicion, entidad, reg_ini, reg_fin)

        elif method in ("buscarareaact", "buscarareaactestr"):
            # Normalizar: NUNCA pasar cadenas vacías a la API
            entidad = _resolve_entidad(kwargs.get("entidad"))
            municipio = _normalize_geo(kwargs.get("municipio"))
            localidad = _normalize_geo(kwargs.get("localidad"))
            ageb = _normalize_geo(kwargs.get("ageb"))
            manzana = _normalize_geo(kwargs.get("manzana"))
            sector = _normalize_geo(kwargs.get("sector"))
            if sector != "0" and not sector.isdigit():
                r = _resolve_scian(sector)
                sector = r if r != "0" else sector
            subsector = _normalize_geo(kwargs.get("subsector"))
            rama = _normalize_geo(kwargs.get("rama"))
            clase = _normalize_geo(kwargs.get("clase"))
            nombre = _str_param(kwargs.get("nombre") or kwargs.get("nombre_establecimiento"), "0")
            reg_ini = _int_param(kwargs.get("registro_inicial"), 1)
            reg_fin = _int_param(kwargs.get("registro_final"), 50)
            id_param = "0"
            estrato = str(_resolve_estrato(kwargs.get("estrato"))) if method == "buscarareaactestr" else None
            url = self._url_buscar_area_act(
                entidad, municipio, localidad, ageb, manzana,
                sector, subsector, rama, clase, nombre,
                reg_ini, reg_fin, id_param, estrato,
            )

        elif method == "cuantificar":
            actividad = _str_param(kwargs.get("actividad"), "0")
            if actividad != "0" and "," not in actividad and not actividad.isdigit():
                r = _resolve_scian(actividad)
                actividad = r if r != "0" else actividad
            area_geografica = _str_param(kwargs.get("area_geografica"), "0")
            estrato = str(_resolve_estrato(kwargs.get("estrato")))
            url = self._url_cuantificar(actividad, area_geografica, estrato)

        if not url:
            return "Error: no se pudo construir la URL. " + self._hint_methods()

        now = time.time()
        cached = self._cache.get(url)
        if cached and cached.get("expires", 0) > now:
            data = cached.get("data")
            if data is not None:
                if method == "ficha":
                    if isinstance(data, list) and len(data) == 1:
                        return _format_ficha(data[0])
                    if isinstance(data, dict):
                        return _format_ficha(data)
                    return str(data)
                if method == "cuantificar":
                    return _format_cuantificar(data)
                if isinstance(data, list):
                    return _format_denue_results(data, method)
                return str(data)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return f"Error: DENUE API devolvió HTTP {r.status_code}. Cuerpo: {r.text[:500]}"
                data = r.json()
                if isinstance(data, dict) and data.get("error"):
                    return f"Error: {data.get('error', data)}"
                self._cache[url] = {"data": data, "expires": now + DENUE_CACHE_TTL_SECONDS}
                if method == "ficha":
                    if isinstance(data, list) and len(data) == 1:
                        return _format_ficha(data[0])
                    if isinstance(data, dict):
                        return _format_ficha(data)
                    return str(data)
                if method == "cuantificar":
                    return _format_cuantificar(data)
                if isinstance(data, list):
                    return _format_denue_results(data, method)
                return str(data)
        except httpx.TimeoutException:
            return "Error: Tiempo de espera agotado al consultar la API DENUE."
        except httpx.RequestError as e:
            return f"Error: Fallo de conexión con DENUE: {e}"
        except Exception as e:
            return f"Error: {e}"
