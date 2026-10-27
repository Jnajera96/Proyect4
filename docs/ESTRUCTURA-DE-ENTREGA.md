# Organización documental de entrega

Estructura incorporada según la referencia del usuario, omitiendo las carpetas
documentales pruebas y metricas.

```text
project-root/
├── README.md
├── docs/
│   ├── SRS/
│   │   ├── IEEE-830-AI-SWE.md
│   │   ├── IEEE-830-AI-SWE.docx
│   │   └── IEEE-830-AI-SWE.pdf
│   ├── arquitectura/
│   │   ├── README.md
│   │   ├── pdf/arquitectura-ai-swe.pdf
│   │   └── drawio/arquitectura-ai-swe.drawio
│   ├── administracion/
│   │   └── gestion-del-proyecto.md
│   └── estimacion/
│       └── estimacion-del-alcance.md
├── diagramas/
│   ├── arquitectura.png
│   └── actividades.png
├── src/ai_swe/
└── frontend/
```

Los README de cada carpeta explican su función y la situación de los artefactos.
La lista de diagramas solicitada por el formato de referencia se conserva en
diagramas/README.md; solo se incluyen como imágenes los ya disponibles.

El código backend permanece en src/ai_swe y el frontend en frontend para mantener
la configuración de construcción actual. No se movieron contratos, dependencias
ni módulos del runtime. Las fuentes canónicas y archivos históricos de docs se
conservan para evitar romper referencias y perder contexto. La suite existente
permanece en el repositorio; se omiten sus carpetas documentales, no se borra código.

La SRS describe requisitos y distingue implementación, preparación parcial y
objetivos. Las actas históricas siguen siendo fuentes fechadas, no un sustituto
de la especificación actual.
