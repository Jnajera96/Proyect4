"""Catalogo de tareas experimentales (F14, `EXP-01`).

**Que es esto.** La bateria de tareas controladas sobre la que se ejecuta la
comparacion `SINGLE_AGENT` vs `MULTI_AGENT` que responde a la pregunta central del
proyecto (docs/06-EVALUATION.md):

    ¿Cuando se justifica usar varios agentes y cuando un unico agente o un flujo
    determinista es mas simple, barato y fiable?

**Por que tareas controladas y no repositorios reales.** Una tarea controlada tiene
un **criterio de exito objetivo y reproducible**: una suite de validacion que falla
antes del cambio y pasa despues. Eso es lo que permite afirmar "esta tarea se
completo" sin juicio humano y sin depender de la red. Un repositorio real anadiria
ruido (dependencias, tamano, fallos ajenos al cambio) y haria la comparacion no
reproducible.

**Por que el modelo va guionizado.** Cada tarea declara la secuencia de propuestas
que el "modelo" devuelve (`propuestas`). El arnes es **offline y determinista**: sin
credenciales, sin red y con el mismo resultado en cada corrida. Es la unica forma de
que la comparacion sea reproducible. **Limitacion declarada**: por tanto mide el
**coste y el beneficio de la orquestacion**, no la calidad de un modelo concreto.
Una tarea con dos propuestas simula lo que de verdad ocurre: el primer intento falla
las pruebas y hace falta una correccion.

**Estructura de cada repositorio de prueba.** El runner materializa
`src/<modulo>.py` (el codigo a cambiar), `tests/test_<modulo>.py` (la suite de
validacion) y un `conftest.py` en la raiz para que `src` sea importable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalTask:
    """Una tarea experimental con criterio de exito objetivo.

    `propuestas` es la secuencia de `CodeProposal` que el modelo guionizado
    devuelve, **en orden**: la primera se usa en el primer paso del Coder, la
    segunda en el siguiente ciclo. Una tarea con una sola propuesta se resuelve al
    primer intento; una con dos, no.
    """

    id: str
    title: str
    category: str
    instruction: str
    files: dict[str, str]
    tests: dict[str, str]
    propuestas: tuple[dict, ...]
    expected_fix: str = field(default="")
    converge: bool = field(default=True)
    """Si **algun** intento del modelo deja la suite de validacion en verde.

    `True` en todas las tareas menos `EXP-13`, que existe precisamente para
    comprobar el control negativo: con un modelo que no converge, el ciclo de
    revision se agota y la ejecucion escala. Se declara como dato -y no se deduce de
    las propuestas- para que una prueba pueda afirmar la propiedad de toda la
    bateria: el **ultimo** intento pasa si y solo si `converge` es `True`.
    """

    @property
    def requiere_correccion(self) -> bool:
        """Si la tarea necesita mas de un intento del Coder."""
        return len(self.propuestas) > 1


def _propuesta(ruta: str, contenido: str, *, rationale: str) -> dict:
    """Una `CodeProposal` de un solo archivo, como la que devolveria el modelo."""
    return {
        "files": [
            {
                "path": ruta,
                "operation": "modify",
                "new_content": contenido,
                "rationale": rationale,
            }
        ],
        "rationale": rationale,
    }


# --------------------------------------------------------------------- catalogo
#
# Trece tareas sobre las ocho categorias que pide la documentacion de evaluacion:
# bugfix, endpoint, validacion, prueba, refactor pequeno, documentacion,
# configuracion y revision de seguridad.
#
#  - Ocho se resuelven al primer intento (el modelo guionizado acierta).
#  - Cuatro (`EXP-02`, `EXP-05`, `EXP-09`, `EXP-11`) exigen **dos** intentos: el
#    primero falla las pruebas y hace falta el ciclo de revision.
#  - Una (`EXP-13`) **no converge**: las dos propuestas fallan, y sirve para
#    comprobar que el ciclo se agota y la ejecucion escala en lugar de girar sin fin.

EXP_01 = EvalTask(
    id="EXP-01",
    title="Corregir el desfase de una paginacion 1-based",
    category="bugfix",
    instruction="corrige la paginacion: la pagina 1 devuelve la lista vacia",
    files={
        "src/paginador.py": (
            "def pagina(elementos: list, tamano: int, numero: int) -> list:\n"
            "    inicio = numero * tamano\n"
            "    return elementos[inicio:inicio + tamano]\n"
        ),
    },
    tests={
        "tests/test_paginador.py": (
            "from src.paginador import pagina\n"
            "\n"
            "ITEMS = [1, 2, 3, 4, 5, 6, 7]\n"
            "\n"
            "\n"
            "def test_la_primera_pagina_empieza_en_el_primer_elemento() -> None:\n"
            "    assert pagina(ITEMS, 3, 1) == [1, 2, 3]\n"
            "\n"
            "\n"
            "def test_la_segunda_pagina_continua() -> None:\n"
            "    assert pagina(ITEMS, 3, 2) == [4, 5, 6]\n"
            "\n"
            "\n"
            "def test_una_pagina_mas_alla_del_final_es_vacia() -> None:\n"
            "    assert pagina(ITEMS, 3, 9) == []\n"
        ),
    },
    propuestas=(
        _propuesta(
            "src/paginador.py",
            "def pagina(elementos: list, tamano: int, numero: int) -> list:\n"
            "    inicio = (numero - 1) * tamano\n"
            "    return elementos[inicio:inicio + tamano]\n",
            rationale="el numero de pagina es 1-based, hay que restar uno para indexar",
        ),
    ),
    expected_fix="restar 1 al numero de pagina antes de calcular el desplazamiento",
)

EXP_02 = EvalTask(
    id="EXP-02",
    title="Corregir el comparador que confunde mayor con mayor o igual",
    category="bugfix",
    instruction="corrige el comparador: dice que 5 es mayor que 5",
    files={
        "src/comparador.py": (
            "def es_mayor(a: float, b: float) -> bool:\n"
            "    return a >= b\n"
        ),
    },
    tests={
        "tests/test_comparador.py": (
            "from src.comparador import es_mayor\n"
            "\n"
            "\n"
            "def test_un_valor_mayor_lo_es() -> None:\n"
            "    assert es_mayor(6, 5) is True\n"
            "\n"
            "\n"
            "def test_un_valor_igual_no_es_mayor() -> None:\n"
            "    assert es_mayor(5, 5) is False\n"
            "\n"
            "\n"
            "def test_un_valor_menor_no_lo_es() -> None:\n"
            "    assert es_mayor(4, 5) is False\n"
        ),
    },
    propuestas=(
        # Primer intento **incorrecto**: cambia el operador pero al reves. Las
        # pruebas lo detectan y el ciclo de revision pide cambios.
        _propuesta(
            "src/comparador.py",
            "def es_mayor(a: float, b: float) -> bool:\n"
            "    return a < b\n",
            rationale="cambio el operador para que no incluya la igualdad",
        ),
        _propuesta(
            "src/comparador.py",
            "def es_mayor(a: float, b: float) -> bool:\n"
            "    return a > b\n",
            rationale="la relacion correcta es estrictamente mayor",
        ),
    ),
    expected_fix="usar `>` en lugar de `>=`",
)

EXP_03 = EvalTask(
    id="EXP-03",
    title="Anadir una ruta al enrutador",
    category="endpoint",
    instruction="corrige el enrutador: falta la ruta 'b'",
    files={
        "src/rutas.py": (
            "def manejar(ruta: str) -> int:\n"
            "    return {'a': 200}.get(ruta, 404)\n"
        ),
    },
    tests={
        "tests/test_rutas.py": (
            "from src.rutas import manejar\n"
            "\n"
            "\n"
            "def test_la_ruta_a_responde_200() -> None:\n"
            "    assert manejar('a') == 200\n"
            "\n"
            "\n"
            "def test_la_ruta_b_responde_201() -> None:\n"
            "    assert manejar('b') == 201\n"
            "\n"
            "\n"
            "def test_una_ruta_desconocida_responde_404() -> None:\n"
            "    assert manejar('z') == 404\n"
        ),
    },
    propuestas=(
        _propuesta(
            "src/rutas.py",
            "def manejar(ruta: str) -> int:\n"
            "    return {'a': 200, 'b': 201}.get(ruta, 404)\n",
            rationale="la ruta 'b' crea un recurso y responde 201",
        ),
    ),
    expected_fix="anadir la entrada 'b' con codigo 201",
)

EXP_04 = EvalTask(
    id="EXP-04",
    title="Endurecer la validacion de correo",
    category="validacion",
    instruction="corrige el validador de correo: acepta direcciones sin dominio",
    files={
        "src/validador.py": (
            "def es_correo_valido(texto: str) -> bool:\n"
            "    return '@' in texto\n"
        ),
    },
    tests={
        "tests/test_validador.py": (
            "from src.validador import es_correo_valido\n"
            "\n"
            "\n"
            "def test_una_direccion_completa_es_valida() -> None:\n"
            "    assert es_correo_valido('ana@ejemplo.com') is True\n"
            "\n"
            "\n"
            "def test_sin_arroba_no_es_valida() -> None:\n"
            "    assert es_correo_valido('ana.ejemplo.com') is False\n"
            "\n"
            "\n"
            "def test_sin_dominio_con_punto_no_es_valida() -> None:\n"
            "    assert es_correo_valido('ana@ejemplo') is False\n"
        ),
    },
    propuestas=(
        _propuesta(
            "src/validador.py",
            "def es_correo_valido(texto: str) -> bool:\n"
            "    if '@' not in texto:\n"
            "        return False\n"
            "    _, _, dominio = texto.partition('@')\n"
            "    return '.' in dominio and not dominio.startswith('.') and not dominio.endswith('.')\n",
            rationale="el dominio tiene que tener un punto que no este en los extremos",
        ),
    ),
    expected_fix="exigir un dominio con punto despues de la arroba",
)

EXP_05 = EvalTask(
    id="EXP-05",
    title="Corregir el contador de numeros pares",
    category="prueba",
    instruction="corrige el contador: cuenta los impares en lugar de los pares",
    files={
        "src/contador.py": (
            "def contar_pares(numeros: list[int]) -> int:\n"
            "    return len([n for n in numeros if n % 2 == 1])\n"
        ),
    },
    tests={
        "tests/test_contador.py": (
            "from src.contador import contar_pares\n"
            "\n"
            "\n"
            "def test_cuenta_los_pares() -> None:\n"
            "    assert contar_pares([1, 2, 3, 4]) == 2\n"
            "\n"
            "\n"
            "def test_el_cero_es_par() -> None:\n"
            "    assert contar_pares([0, 1]) == 1\n"
            "\n"
            "\n"
            "def test_una_lista_sin_pares_da_cero() -> None:\n"
            "    assert contar_pares([1, 3, 5]) == 0\n"
        ),
    },
    propuestas=(
        # Primer intento incorrecto: invierte la paridad pero sigue sin contar el 0.
        _propuesta(
            "src/contador.py",
            "def contar_pares(numeros: list[int]) -> int:\n"
            "    return len([n for n in numeros if n % 2 == 0 and n != 0])\n",
            rationale="cuento los pares excluyendo el cero",
        ),
        _propuesta(
            "src/contador.py",
            "def contar_pares(numeros: list[int]) -> int:\n"
            "    return len([n for n in numeros if n % 2 == 0])\n",
            rationale="el resto de dividir cero entre dos es cero, luego el cero es par",
        ),
    ),
    expected_fix="comparar el resto con 0 sin excluir el cero",
)

EXP_06 = EvalTask(
    id="EXP-06",
    title="Normalizar guiones repetidos en un identificador",
    category="refactor",
    instruction="corrige el normalizador: deja guiones repetidos al colapsar espacios",
    files={
        "src/texto.py": (
            "def normalizar(texto: str) -> str:\n"
            "    return texto.strip().lower().replace(' ', '-')\n"
        ),
    },
    tests={
        "tests/test_texto.py": (
            "from src.texto import normalizar\n"
            "\n"
            "\n"
            "def test_los_espacios_se_convierten_en_guiones() -> None:\n"
            "    assert normalizar('hola mundo') == 'hola-mundo'\n"
            "\n"
            "\n"
            "def test_los_espacios_repetidos_no_dejan_guiones_repetidos() -> None:\n"
            "    assert normalizar('hola   mundo') == 'hola-mundo'\n"
            "\n"
            "\n"
            "def test_los_extremos_no_dejan_guiones() -> None:\n"
            "    assert normalizar('  hola  ') == 'hola'\n"
        ),
    },
    propuestas=(
        _propuesta(
            "src/texto.py",
            "def normalizar(texto: str) -> str:\n"
            "    return '-'.join(texto.split()).lower()\n",
            rationale="`split()` sin argumento colapsa los espacios y descarta los extremos",
        ),
    ),
    expected_fix="usar split()/join en lugar de replace(' ', '-')",
)

EXP_07 = EvalTask(
    id="EXP-07",
    title="Documentar la funcion publica del modulo",
    category="documentacion",
    instruction="corrige la documentacion: la funcion publica no tiene docstring",
    files={
        "src/api_mod.py": (
            "def area_circulo(radio: float) -> float:\n"
            "    return 3.141592653589793 * radio * radio\n"
        ),
    },
    tests={
        "tests/test_api_mod.py": (
            "from src.api_mod import area_circulo\n"
            "\n"
            "\n"
            "def test_la_funcion_esta_documentada() -> None:\n"
            "    assert area_circulo.__doc__ is not None\n"
            "    assert area_circulo.__doc__.strip()\n"
            "\n"
            "\n"
            "def test_la_documentacion_dice_que_devuelve() -> None:\n"
            "    assert 'devuelve' in area_circulo.__doc__.lower()\n"
            "\n"
            "\n"
            "def test_el_calculo_sigue_siendo_correcto() -> None:\n"
            "    assert round(area_circulo(1.0), 4) == 3.1416\n"
        ),
    },
    propuestas=(
        _propuesta(
            "src/api_mod.py",
            "def area_circulo(radio: float) -> float:\n"
            "    \"\"\"Devuelve el area de un circulo de radio `radio`.\n"
            "\n"
            "    Usa pi con doble precision; no redondea el resultado.\n"
            "    \"\"\"\n"
            "    return 3.141592653589793 * radio * radio\n",
            rationale="documenta que devuelve y con que precision calcula",
        ),
    ),
    expected_fix="anadir un docstring que declare que devuelve la funcion",
)

EXP_08 = EvalTask(
    id="EXP-08",
    title="Leer el tiempo de espera de la configuracion con valor por defecto",
    category="configuracion",
    instruction="corrige la configuracion: el tiempo de espera por defecto es 5 y debe ser 30",
    files={
        "src/config_mod.py": (
            "def tiempo_de_espera(entorno: dict) -> int:\n"
            "    return int(entorno.get('TIMEOUT', 5))\n"
        ),
    },
    tests={
        "tests/test_config_mod.py": (
            "from src.config_mod import tiempo_de_espera\n"
            "\n"
            "\n"
            "def test_sin_variable_usa_treinta() -> None:\n"
            "    assert tiempo_de_espera({}) == 30\n"
            "\n"
            "\n"
            "def test_la_variable_manda() -> None:\n"
            "    assert tiempo_de_espera({'TIMEOUT': '12'}) == 12\n"
        ),
    },
    propuestas=(
        _propuesta(
            "src/config_mod.py",
            "def tiempo_de_espera(entorno: dict) -> int:\n"
            "    return int(entorno.get('TIMEOUT', 30))\n",
            rationale="el valor por defecto acordado es 30 segundos",
        ),
    ),
    expected_fix="cambiar el valor por defecto de 5 a 30",
)

EXP_09 = EvalTask(
    id="EXP-09",
    title="Impedir que una ruta relativa escape del directorio base",
    category="revision de seguridad",
    instruction="corrige la resolucion de rutas: permite escapar del directorio base",
    files={
        "src/archivos.py": (
            "from pathlib import Path\n"
            "\n"
            "\n"
            "def resolver(base: str, nombre: str):\n"
            "    return Path(base) / nombre\n"
        ),
    },
    tests={
        "tests/test_archivos.py": (
            "import tempfile\n"
            "from pathlib import Path\n"
            "\n"
            "from src.archivos import resolver\n"
            "\n"
            "\n"
            "def test_una_ruta_normal_se_resuelve() -> None:\n"
            "    with tempfile.TemporaryDirectory() as base:\n"
            "        esperado = (Path(base) / 'a.txt').resolve()\n"
            "        assert resolver(base, 'a.txt') == esperado\n"
            "\n"
            "\n"
            "def test_una_ruta_que_sube_es_rechazada() -> None:\n"
            "    with tempfile.TemporaryDirectory() as base:\n"
            "        assert resolver(base, '../secreto.txt') is None\n"
            "\n"
            "\n"
            "def test_una_ruta_absoluta_es_rechazada() -> None:\n"
            "    with tempfile.TemporaryDirectory() as base:\n"
            "        absoluta = Path(base).anchor + 'passwd'\n"
            "        assert resolver(base, absoluta) is None\n"
        ),
    },
    propuestas=(
        # Primer intento incompleto: corta la subida por arriba pero deja pasar la
        # ruta absoluta. La suite lo detecta.
        _propuesta(
            "src/archivos.py",
            "from pathlib import Path\n"
            "\n"
            "\n"
            "def resolver(base: str, nombre: str):\n"
            "    if nombre.startswith('..'):\n"
            "        return None\n"
            "    return Path(base) / nombre\n",
            rationale="rechazo los nombres que empiezan por dos puntos",
        ),
        _propuesta(
            "src/archivos.py",
            "from pathlib import Path\n"
            "\n"
            "\n"
            "def resolver(base: str, nombre: str):\n"
            "    destino = (Path(base) / nombre).resolve()\n"
            "    raiz = Path(base).resolve()\n"
            "    if destino != raiz and raiz not in destino.parents:\n"
            "        return None\n"
            "    return destino\n",
            rationale="compruebo la ruta ya resuelta contra la raiz, no la cadena",
        ),
    ),
    expected_fix="comparar la ruta resuelta contra la raiz en lugar de mirar la cadena",
)

EXP_10 = EvalTask(
    id="EXP-10",
    title="Convertir a numero antes de sumar",
    category="bugfix",
    instruction="corrige la suma: concatena los textos en lugar de sumar numeros",
    files={
        "src/suma.py": (
            "def suma(valores: list) -> int:\n"
            "    return sum(valores)\n"
        ),
    },
    tests={
        "tests/test_suma.py": (
            "from src.suma import suma\n"
            "\n"
            "\n"
            "def test_suma_enteros() -> None:\n"
            "    assert suma([1, 2, 3]) == 6\n"
            "\n"
            "\n"
            "def test_suma_textos_numericos() -> None:\n"
            "    assert suma(['1', '2', '3']) == 6\n"
        ),
    },
    propuestas=(
        _propuesta(
            "src/suma.py",
            "def suma(valores: list) -> int:\n"
            "    return sum(int(v) for v in valores)\n",
            rationale="convierto cada valor a entero antes de acumular",
        ),
    ),
    expected_fix="convertir cada elemento a int antes de sumar",
)

EXP_11 = EvalTask(
    id="EXP-11",
    title="Rechazar un limite no positivo",
    category="endpoint",
    instruction="corrige el limitador: un limite de cero devuelve la lista entera",
    files={
        "src/limitador.py": (
            "def limitar(elementos: list, maximo: int) -> list:\n"
            "    return elementos[:maximo]\n"
        ),
    },
    tests={
        "tests/test_limitador.py": (
            "import pytest\n"
            "\n"
            "from src.limitador import limitar\n"
            "\n"
            "\n"
            "def test_limita_la_lista() -> None:\n"
            "    assert limitar([1, 2, 3], 2) == [1, 2]\n"
            "\n"
            "\n"
            "def test_un_limite_mayor_que_la_lista_la_deja_igual() -> None:\n"
            "    assert limitar([1, 2], 10) == [1, 2]\n"
            "\n"
            "\n"
            "def test_un_limite_cero_es_un_error() -> None:\n"
            "    with pytest.raises(ValueError):\n"
            "        limitar([1, 2, 3], 0)\n"
            "\n"
            "\n"
            "def test_un_limite_negativo_es_un_error() -> None:\n"
            "    with pytest.raises(ValueError):\n"
            "        limitar([1, 2, 3], -1)\n"
        ),
    },
    propuestas=(
        # Primer intento incompleto: solo cubre el cero, no el negativo.
        _propuesta(
            "src/limitador.py",
            "def limitar(elementos: list, maximo: int) -> list:\n"
            "    if maximo == 0:\n"
            "        raise ValueError('el limite tiene que ser positivo')\n"
            "    return elementos[:maximo]\n",
            rationale="rechazo el limite cero",
        ),
        _propuesta(
            "src/limitador.py",
            "def limitar(elementos: list, maximo: int) -> list:\n"
            "    if maximo <= 0:\n"
            "        raise ValueError('el limite tiene que ser positivo')\n"
            "    return elementos[:maximo]\n",
            rationale="un limite negativo tambien es invalido: la comprobacion es <= 0",
        ),
    ),
    expected_fix="rechazar todo limite <= 0, no solo el cero",
)

EXP_12 = EvalTask(
    id="EXP-12",
    title="Rechazar un nombre vacio",
    category="validacion",
    instruction="corrige el normalizador de nombres: acepta la cadena vacia",
    files={
        "src/nombres.py": (
            "def normalizar_nombre(texto: str) -> str:\n"
            "    return texto.strip().title()\n"
        ),
    },
    tests={
        "tests/test_nombres.py": (
            "import pytest\n"
            "\n"
            "from src.nombres import normalizar_nombre\n"
            "\n"
            "\n"
            "def test_normaliza_mayusculas_y_espacios() -> None:\n"
            "    assert normalizar_nombre('  ana maria  ') == 'Ana Maria'\n"
            "\n"
            "\n"
            "def test_una_cadena_vacia_es_un_error() -> None:\n"
            "    with pytest.raises(ValueError):\n"
            "        normalizar_nombre('   ')\n"
        ),
    },
    propuestas=(
        _propuesta(
            "src/nombres.py",
            "def normalizar_nombre(texto: str) -> str:\n"
            "    limpio = texto.strip()\n"
            "    if not limpio:\n"
            "        raise ValueError('el nombre no puede estar vacio')\n"
            "    return limpio.title()\n",
            rationale="un nombre vacio no es un nombre: se declara el error",
        ),
    ),
    expected_fix="lanzar ValueError cuando el nombre queda vacio tras limpiarlo",
)


EXP_13 = EvalTask(
    id="EXP-13",
    title="Devolver `None` en lugar de fallar al dividir entre cero",
    category="bugfix",
    instruction="corrige la division: revienta cuando el divisor es cero",
    files={
        "src/division.py": (
            "def dividir(a: float, b: float):\n"
            "    return a / b\n"
        ),
    },
    tests={
        "tests/test_division.py": (
            "from src.division import dividir\n"
            "\n"
            "\n"
            "def test_una_division_normal() -> None:\n"
            "    assert dividir(6, 3) == 2.0\n"
            "\n"
            "\n"
            "def test_dividir_entre_cero_devuelve_none() -> None:\n"
            "    assert dividir(1, 0) is None\n"
        ),
    },
    # **Ninguna de las dos propuestas es correcta.** Es la tarea que demuestra que
    # el multiagente no es magia: con un modelo que no converge, el ciclo de
    # revision se agota y la ejecucion **escala** en lugar de girar sin fin. Es la
    # guarda `REGLA 2` vista desde la evaluacion.
    propuestas=(
        _propuesta(
            "src/division.py",
            "def dividir(a: float, b: float):\n"
            "    if b == 0:\n"
            "        return 0\n"
            "    return a / b\n",
            rationale="si el divisor es cero devuelvo cero",
        ),
        _propuesta(
            "src/division.py",
            "def dividir(a: float, b: float):\n"
            "    if b == 0:\n"
            "        return False\n"
            "    return a / b\n",
            rationale="si el divisor es cero devuelvo un valor falsy",
        ),
    ),
    expected_fix="devolver `None` (no 0 ni False) cuando el divisor es cero",
    converge=False,
)


TAREAS: tuple[EvalTask, ...] = (
    EXP_01,
    EXP_02,
    EXP_03,
    EXP_04,
    EXP_05,
    EXP_06,
    EXP_07,
    EXP_08,
    EXP_09,
    EXP_10,
    EXP_11,
    EXP_12,
    EXP_13,
)


def tarea_por_id(identificador: str) -> EvalTask:
    """Busca una tarea por su identificador. Falla si no existe, en vez de `None`."""
    for tarea in TAREAS:
        if tarea.id == identificador:
            return tarea
    raise KeyError(f"no existe la tarea experimental '{identificador}'")
