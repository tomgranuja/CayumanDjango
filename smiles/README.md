# SMileS - Sistema de Gestión Escolar

## Introducción

SMileS (School Management System) es una evolución del sistema cayuman, diseñado para ofrecer mayor flexibilidad y personalización. Este documento explica cómo los modelos de SMileS se relacionan con la implementación actual de cayuman, para facilitar la comprensión y transición entre ambos sistemas.

## Filosofía de Diseño

Mientras que cayuman fue construido con estructuras predefinidas (workshops, cycles, etc.), SMileS adopta un enfoque configurable donde las escuelas pueden definir sus propias estructuras organizativas a través de la interfaz de administración de Django.

## Modelos Principales y sus Equivalentes en Cayuman

### Miembros (Member)

**En Cayuman**: Usuario + información básica.

**En SMileS**: El modelo `Member` extiende al usuario de Django con un campo `metadata` flexible que permite almacenar cualquier información adicional (condiciones especiales, adaptaciones educativas, etc.) sin necesidad de modificar la estructura de la base de datos.

### Grupos (Group)

**En Cayuman**: Estructuras fijas como "Cycles" y "Grades".

**En SMileS**: El modelo `Group` permite definir cualquier tipo de agrupación (grados, ciclos, equipos, casas, etc.) a través del campo `group_type`. Cada grupo puede tener sus propias propiedades y metadatos, además de estructuras jerárquicas mediante relaciones padre-hijo.

### Períodos (Term)

**En Cayuman**: `Period` para períodos de workshops con fechas específicas de inscripción.

**En SMileS**: El modelo `Term` representa cualquier tipo de período temporal (semestres, trimestres, períodos de workshop, años académicos) con el campo `term_type`. Incluye configuración flexible para períodos de inscripción a través de métodos como `add_enrollment_period()` y `get_enrollment_periods()`.

### Asignaturas (Subject y SubjectType)

**En Cayuman**: `Workshop` con comportamiento predefinido.

**En SMileS**:

- `SubjectType` define tipos de asignaturas (Workshop, Asignatura Académica, Extracurricular, etc.)
- `Subject` representa asignaturas concretas (Matemáticas, Carpintería, etc.)
- `SubjectOffering` vincula asignaturas con términos específicos, docentes y grupos elegibles

### Ofertas de Asignaturas y Períodos de Inscripción

**En Cayuman**: Fechas de inscripción fijas para workshops.

**En SMileS**: Cada `SubjectOffering` puede tener sus propias fechas de:

- `preview_date`: Cuándo se hace visible la oferta para estudiantes
- `enrollment_start`: Cuándo comienza la inscripción
- `enrollment_end`: Cuándo finaliza la inscripción

Además, el servicio `EnrollmentService` centraliza la lógica de negocio relacionada con inscripciones.

### Sistema de Horarios

**En Cayuman**: Sistema de horarios limitado.

**En SMileS**: Sistema completo con:

- `ActivityType` y `Activity`: Tipos de actividades que pueden programarse
- `TimeSlot`: Franjas horarias recurrentes
- `ScheduleTemplate`: Plantillas de horarios aplicables a grupos
- `ScheduleAssignment`: Asignación de actividades a franjas horarias
- `MemberSchedule` y `MemberScheduleOverride`: Horarios individuales y sus excepciones
- `SpecialDay`: Días especiales (festivos, eventos) que afectan a los horarios normales

### Asistencia

**En Cayuman**: Registro básico de asistencia.

**En SMileS**: Modelo `Attendance` con capacidad para registrar:

- Asistencia/ausencia
- Salidas anticipadas
- Llegadas tardías
- Notas adicionales
- Metadatos flexibles

## Ventajas del Nuevo Sistema

1. **Flexibilidad Total**: Las escuelas pueden definir sus propias estructuras organizativas, términos y tipos de asignaturas.

2. **Datos Extendibles**: Campos de metadatos JSON permiten almacenar información adicional sin modificar el esquema de la base de datos.

3. **Sistema de Horarios Completo**: Gestión detallada de horarios regulares, excepciones y días especiales.

4. **Gestión de Inscripciones Mejorada**: Control preciso sobre cuándo y cómo los estudiantes pueden inscribirse en asignaturas.

5. **Jerarquías y Relaciones**: Soporte para estructuras jerárquicas (grupos padres e hijos) y relaciones complejas entre entidades.

## Cómo Migrar de Cayuman a SMileS

Para migrar desde cayuman:

1. **Cycles → Groups**: Convertir los ciclos a grupos con `group_type = "Cycle"`
2. **Periods → Terms**: Convertir períodos a términos con `term_type` apropiado
3. **Workshops → Subjects**: Convertir workshops a asignaturas con un `SubjectType` adecuado
4. **Workshop Periods → SubjectOfferings**: Convertir las ofertas de workshops a `SubjectOfferings`
5. **Student Cycles → MemberGroupAssignments**: Convertir asignaciones de estudiantes a ciclos al nuevo sistema

## Personalización Avanzada

El sistema SMileS está diseñado para adaptarse a diferentes modelos educativos:

- **Escuelas tradicionales**: Configurar grupos como grados y asignaturas académicas
- **Escuelas alternativas**: Configurar grupos por habilidades y asignaturas por proyectos
- **Homeschooling cooperativo**: Configurar grupos por familias y asignaturas por mentores

## Consultas Comunes

### ¿Cómo funcionan los períodos de inscripción?

1. A nivel de término, se pueden definir períodos generales usando `term.add_enrollment_period()`
2. A nivel de asignatura, cada `SubjectOffering` tiene sus propios campos para fechas de publicación e inscripción
3. El servicio `EnrollmentService` proporciona métodos para verificar disponibilidad e inscribir miembros

### ¿Cómo se configuran los horarios?

1. Crear `TimeSlot` para definir franjas horarias (días y horas)
2. Crear `Activity` para definir actividades a programar
3. Crear `ScheduleTemplate` y vincular con grupos y términos
4. Crear `ScheduleAssignment` para asignar actividades a franjas horarias
5. Los horarios individuales (`MemberSchedule`) se generan a partir de plantillas

### ¿Cómo se manejan las excepciones?

- **Días especiales**: Usar `SpecialDay` para festivos, eventos, etc.
- **Excepción individual**: Usar `MemberScheduleOverride` para cambios en el horario de un miembro específico
