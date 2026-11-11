# Proyecto01DASH_FLASK

* `El grupo de carpetas del dataset estan en la siguiente ruta`
- https://drive.google.com/drive/folders/1UPy3Ulwac5Cq_RjvvAhWz1Zbzm0MKKK2


Dashboard web desarrollado con Flask para visualizar indicadores operativos de logística y compensaciones. La aplicación permite consultar métricas de guías, piezas, rezagos, confirmaciones, tareas y procesos, además de gestionar usuarios, áreas y permisos por dashboard.

## Descripción general

Este proyecto está pensado para operar como un panel ejecutivo de seguimiento de la operación logística. Se conecta con archivos Parquet almacenados en la carpeta `dataset`, procesa la información mediante un servicio de datos y genera vistas analíticas con filtros por periodo, regional, canal, bodega y otros atributos.

La aplicación incluye:

- Autenticación de usuarios con sesión segura.
- Selección de área y dashboard por usuario.
- Módulos analíticos para indicadores clave.
- Vista administrativa para crear usuarios y cambiar contraseñas.
- Exportación de reportes en CSV.
- Carga de datos desde archivos parquet con cacheo de cubos para mayor rendimiento.

## ¿Qué muestra el dashboard?

La aplicación está orientada a métricas de servicio y operación, entre las principales se encuentran:

- Total de guías y piezas registradas.
- Guías en compensación y en rezago.
- Confirmaciones por canal y regional.
- Vejez por tipo de proceso.
- Tareas pendientes y cerradas.
- Comparativos por bodega, regional y proceso.
- Reporte detallado con exportación.

En la práctica, el dashboard sirve para analizar el comportamiento de la operación, detectar cuellos de botella y evidenciar áreas con mayor incidencia en compensaciones o rezagos.

## Arquitectura del proyecto

La estructura principal del proyecto es la siguiente:

- `app.py`: aplicación principal de Flask, rutas, sesión, acceso por roles y renderizado del dashboard.
- `analytics.py`: generación de KPIs, tablas e insights que alimentan cada vista del panel.
- `data_service.py`: construcción de cubos agregados desde archivos parquet, filtros y cálculo de métricas.
- `database.py`: base SQLite con usuarios, áreas, dashboards y permisos.
- `templates/`: plantillas HTML para login, área, dashboard y panel base.
- `static/`: archivos estáticos del frontend (CSS, JS, imágenes si aplica).
- `dataset/`: archivos fuente en formato Parquet.
- `cache/`: caché de cubos generados para optimizar tiempos de carga.
- `dashboard.db`: base de datos SQLite local de la aplicación.

## Requisitos

Antes de ejecutar el proyecto, asegúrate de tener instalado:

- Python 3.10 o superior
- pip
- Entorno virtual (recomendado)

Además, la aplicación espera tener los archivos de datos en la carpeta `dataset` en formato Parquet.

## Instalación

1. Clona o descarga este repositorio.
2. Entra a la carpeta del proyecto.
3. Crea un entorno virtual:

```bash
python -m venv .venv
```

4. Activa el entorno virtual:

- En Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

- En Linux/macOS:

```bash
source .venv/bin/activate
```

5. Instala las dependencias:

```bash
pip install -r requirements.txt
```

## Ejecución

Una vez instaladas las dependencias, inicia la aplicación con:

```bash
python app.py
```

La aplicación quedará disponible en:

```text
http://localhost:5000
```

Si deseas usar una variable de entorno para la clave secreta o la base de datos puedes configurarlas antes de arrancar la app:

```bash
set SECRET_KEY=mi_clave_segura
set DASHBOARD_DB=dashboard.db
python app.py
```

## Acceso inicial

La primera vez que se ejecuta la aplicación, se crea automáticamente una base SQLite con un usuario administrador por defecto.

Credenciales por defecto:

- Usuario: `admin`
- Contraseña: `admin123`

Es recomendable cambiar la contraseña en producción o definir una contraseña distinta mediante la variable de entorno `ADMIN_PASSWORD` antes de la primera ejecución.

## Roles y permisos

La aplicación separa la lógica de autenticación por roles:

- `admin`: tiene acceso a administración completa de usuarios y permisos.
- `user`: puede acceder a los dashboards según el área asignada.

Desde la ruta `/admin` se pueden:

- Crear nuevos usuarios.
- Cambiar contraseñas.
- Activar o desactivar usuarios.
- Gestionar el acceso al sistema.

## Flujos principales del sistema

### 1. Inicio de sesión

El usuario accede a `/login` y si las credenciales son correctas, se crea la sesión y se redirige a la selección de áreas.

### 2. Selección de área

La vista `/areas` muestra los distintos espacios operativos disponibles para el usuario. Cada área tiene sus dashboards asociados.

### 3. Acceso a dashboard

Cuando el usuario abre un dashboard, la sesión guarda el contexto del área y del tablero. A partir de ahí la aplicación carga los cubos de datos, aplica filtros y construye las views del módulo.

### 4. Visualización analítica

Cada página del dashboard incluye:

- KPI principal
- Gráficos de distribución
- Tablas comparativas
- Insights textuales para interpretación del análisis
- Filtros dinámicos

### 5. Exportación

La ruta `/reporte/export.csv` permite exportar el reporte detallado a CSV para análisis externo en Excel u otras herramientas.

## Datos y procesamiento

El sistema no consulta la base de datos relacional para cada vista; en su lugar, procesa archivos Parquet y crea cubos agregados para responder rápidamente.

Esto permite:

- Mejor rendimiento al consultar grandes volúmenes de información.
- Reutilización de métricas ya calculadas.
- Aplicación consistente de filtros a todas las vistas.

Los datos principales se gestionan en `data_service.py`, donde se construyen estructuras como:

- `base`: indicadores generales de guías y piezas.
- `piezas`: distribución por número de piezas.
- `vejez`: análisis por rangos de vejez.
- `tareas`: seguimiento de tareas pendientes y cerradas.
- `procesos`: análisis por dimensión o proceso.

## Variables de entorno útiles

Puedes ajustar la configuración del proyecto con estas variables:

- `SECRET_KEY`: clave para la sesión de Flask.
- `ADMIN_PASSWORD`: contraseña del usuario administrador inicial.
- `DASHBOARD_DB`: ruta de la base SQLite de la aplicación.
- `SESSION_COOKIE_SECURE`: habilita cookies seguras en producción.

## Recomendaciones para producción

Antes de desplegar la app en un entorno real, considera:

- Cambiar la clave `SECRET_KEY` por una valor seguro.
- Configurar credenciales reales para usuarios.
- Usar un servidor WSGI como Gunicorn o uWSGI.
- Mantener la base SQLite para entornos pequeños o migrar a un motor más robusto en producción.
- Validar los archivos Parquet de entrada antes de cargar el dashboard.

## Solución de problemas comunes

### No se ve la información en el dashboard

Verifica que exista la carpeta `dataset` con los archivos Parquet esperados y que los nombres coincidan con los definidos en `data_service.py`.

### Error de acceso o login

Asegúrate de estar usando las credenciales correctas y que el usuario no esté deshabilitado desde `/admin`.

### La aplicación no inicia

Revisa si faltan dependencias y asegúrate de que estás ejecutando el proyecto desde el entorno virtual correcto.

## Conclusión

Este proyecto combina Flask, SQLite y procesamiento de datos mediante Parquet para ofrecer un panel analítico de operación logística con autenticación, permisos y visualización de indicadores clave. Su enfoque está orientado a la toma de decisiones operativas, la identificación de desbalances y la supervisión de indicadores críticos en tiempo real.

Si quieres, en una siguiente iteración puedo ampliar este README con:

- una sección de captura de pantallas,
- una guía de despliegue en Render/Heroku/VPS,
- o una explicación más técnica de cada archivo del proyecto.
