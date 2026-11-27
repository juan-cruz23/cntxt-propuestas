# Contexto Maestro CNTXT (Playbook R.E.D.)

## Identidad y Propósito
- **Empresa:** CNTXT (Contexto Arquitectura) — Casa de Diseño en Medellín, Colombia.
- **Propósito:** "Diseñamos con tecnología para crear vidas extraordinarias."
- **MEGA 2030:** Transformar la vida de 10.000 familias, superar $100.000 millones COP en ventas y sostener un EBITDA del 30%.
- **Filosofía:** Ecosistema de alto rendimiento (Biocenosis: talento, tecnología, procesos disruptivos vs Biotopo: mercado). Primero el oxígeno (caja/rentabilidad), luego la magia (diseño y experiencia extraordinaria).

## 6 Conceptos Maestros (ADN CNTXT)
1. **Well Being (Bienestar):** Slow Life, paz mental, calidad de vida por encima de acumular m².
2. **Context (Contexto):** Lectura profunda del territorio, clima, paisaje, cultura y forma de vivir.
3. **Disruption (Disrupción):** Cuestionar soluciones convencionales con propuestas audaces y diferenciales.
4. **Smartness (Inteligencia):** Smart Life, tecnología, eficiencia y sostenibilidad.
5. **Customization (Hiper Personalización):** Soluciones únicas que reflejan la identidad del cliente, huyendo de lo genérico.
6. **Storytelling (Experiencia):** Narrativa y comunicación emocional que enamoran antes de construir.

## Modelos de Negocio
- **MADE:** Diseño arquitectónico, urbano, interior, comercial o visualización 100% a la medida, estructurado en Fases 1 (conceptualización/anteproyecto), Fase 2 (desarrollo arquitectónico/especificaciones) y Fase 3 (detalle constructivo para ejecución de obra).
- **SELECT:** Vivienda campestre por catálogo (Essential $5M, Advanced $7M, Premium $10M COP base) + Personal Shopper de lote (Lite / Advanced).

## Perfiles de Cliente
### B2B — ICP Corporativo
- **Quiénes son:** Promotoras, constructoras-desarrolladoras, gerencias inmobiliarias, fondos/FICs/fiducias, real estate turístico/wellness y empresas con banco de tierras (Colombia, Panamá, República Dominicana, Costa Rica).
- **Dolores clave:**
  1. Comoditización ("un lote más" o "un proyecto más").
  2. Techo de precio y margen estrangulado (no poder defender un precio premium por m²).
  3. Brecha entre plano técnico frío y emoción comercial.
  4. Parálisis en preventas / velocidad de absorción (dificultad para vender intangibles sobre planos).

### B2C — Avatares
- **Victoria (Seguridad y Familia):** Busca entorno sano para su hijo y desconfía de constructores tradicionales.
- **Ana Lucía (Paz Mental y Slow Life):** Busca salir del ritmo frenético urbano, tranquilidad con pareja y mascotas.
- **Mateo (Desarrollo y Monetización):** Tiene lote familiar desaprovechado, busca asesoría por etapas para rentabilizar.
- **Luis (Estatus, Legado e Inversión Segura):** Diversificar patrimonio para retiro sin invertir su propio tiempo/energía.

## Reglas de Propuesta CNTXT
- **SIEMPRE generar exactamente 3 Niveles de Acceso ordenados de MÁS a MENOS** (anclaje de valor: Nivel 1 Integral/Full -> Nivel 2 Estratégico/Intermedio -> Nivel 3 Esencial/Entrada).
- **Moneda base:** COP (sin IVA 19%, `aplica_iva=True`).
- **Tono:** Aspiracional, estratégico, preciso, humano y orientado a valor/experiencia. Nunca genérico ni puramente técnico-frío.
- **Auditoria contra CNTXT Briefs:** Extraer siempre los 14 campos exactos de `ProjectBrief` (`title`, `subtitle`, `project_category`, `estimated_area`, `operative_line` [VISUALIZACION|DISENO], `scope_phase` [FASE_1|FASE_2|FASE_3], `description`, `architectural_program`, `design_premises`, `conceptual_approach`, `essential_deliverables`, `temporal_conditioning`, `reference_images_url`, `status`) y listar explícitamente cualquier dato clave faltante.
