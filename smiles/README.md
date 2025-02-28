# SMileS - Sistema de Gestión Escolar

## Introducción

SMileS (School Management System) es una evolución del sistema Cayuman, diseñado para ofrecer mayor flexibilidad y personalización. Este documento explica cómo los modelos de SMileS se relacionan con la implementación actual de Cayuman, para facilitar la comprensión y transición entre ambos sistemas.

## Filosofía de Diseño

Mientras que Cayuman fue construido con estructuras predefinidas (workshops, cycles, etc.), SMileS adopta un enfoque configurable donde las escuelas pueden definir sus propias estructuras organizativas a través de la interfaz de administración de Django.

## Modelos Principales y sus Equivalentes en Cayuman

### Modelo Base (BaseModel)

**En Cayuman**: No existía un modelo base explícito.

**En SMileS**: Modelo abstracto que proporciona campos comunes (created_at, updated_at) para todos los demás modelos, garantizando consistencia en el seguimiento de creación y modificación de registros.

### Miembros (Member)

**En Cayuman**: Usuario + información básica con propiedades como is_student e is_teacher.

**En SMileS**:
- Utiliza el mismo modelo Member de Cayuman para mantener compatibilidad.
- Implementa las mismas propiedades is_student e is_teacher para verificar pertenencia a grupos.
- Añade current_student_cycle para obtener el MemberGroupAssignment más reciente (reemplazando la funcionalidad del StudentCycle).
- Migra los métodos is_enabled_to_enroll() e is_schedule_full() para mantener la lógica de permisos.

### Grupos (Group)

**En Cayuman**: Estructuras fijas como "Cycles" (ciclos) con campos predefinidos.

**En SMileS**:
- El modelo `Group` reemplaza directamente al modelo `Cycle` de Cayuman.
- Utiliza el campo `group_type="Cycle"` para identificar grupos que funcionan como ciclos en Cayuman.
- Incorpora fields adicionales como is_primary, properties (JSON) y metadata (JSON) para mayor flexibilidad.
- Permite estructuras jerárquicas mediante la relación parent, posibilitando agrupaciones más complejas.
- En la migración, cada Cycle se convierte en un Group con group_type="Cycle".

### Períodos (Term)

**En Cayuman**: `Period` para períodos de workshops con fechas específicas de inscripción (enrollment_start/end).

**En SMileS**:
- El modelo `Term` reemplaza directamente al modelo `Period` de Cayuman.
- Utiliza `term_type="Workshop Period"` para identificar términos que funcionan como períodos en Cayuman.
- Implementa los mismos métodos que Period:
  - is_current() para verificar si el término es actual
  - is_in_the_past() para verificar si el término ya finalizó
  - is_in_the_future() para verificar si el término aún no comienza
  - is_enabled_to_preview() para verificar si la información puede mostrarse
  - is_enabled_to_enroll() para verificar si la inscripción está permitida
- La funcionalidad de enrollment_start/end se traslada a objetos Event de tipo "Enrollment".
- Añade get_enrollment_periods() y add_enrollment_period() para mayor flexibilidad.

### Asignaturas (Subject y SubjectType)

**En Cayuman**: `Workshop` con comportamiento predefinido y campos fijos.

**En SMileS**:
- `SubjectType` define tipos de asignaturas. Para emular Cayuman, se crea un tipo "Workshop".
- `Subject` reemplaza directamente al modelo `Workshop` de Cayuman.
- En la migración, cada Workshop se convierte en un Subject con type="Workshop".
- El campo metadata almacena información adicional como full_name que existía en Workshop.

### Ofertas de Asignaturas (SubjectOffering)

**En Cayuman**: `WorkshopPeriod` vinculaba talleres a períodos, maestros y horarios.

**En SMileS**:
- `SubjectOffering` reemplaza directamente al modelo `WorkshopPeriod` de Cayuman.
- Implementa los mismos métodos críticos:
  - count_classes() para calcular el total de clases en el período
  - count_students() para contar estudiantes inscritos
  - remaining_quota() para calcular cupos disponibles
- Añade validación de horarios y fechas de inscripción similar a WorkshopPeriod.
- Se vincula con Event para manejar períodos de inscripción (reemplazando enrollment_start/end).

### Horarios (TimeSlot)

**En Cayuman**: `Schedule` definía bloques de tiempo semanales con día y horas.

**En SMileS**:
- `TimeSlot` reemplaza directamente al modelo `Schedule` de Cayuman.
- Mantiene la misma validación para evitar superposiciones de horarios en el mismo día.
- Incluye los mismos campos day_of_week, time_start y time_end.
- En la migración, cada Schedule se convierte en un TimeSlot manteniendo sus datos originales.

### Asignación a Ciclos (MemberGroupAssignment)

**En Cayuman**: `StudentCycle` vinculaba estudiantes a ciclos y talleres.

**En SMileS**:
- `MemberGroupAssignment` reemplaza directamente al modelo `StudentCycle` de Cayuman.
- Implementa los métodos clave:
  - subject_offerings_by_time_slot() (adaptado de workshop_periods_by_schedule())
  - subject_offerings_by_term() (adaptado de workshop_periods_by_period())
  - is_schedule_full() para verificar si todos los bloques de horario están cubiertos
  - is_enabled_to_enroll() para validar posibilidad de inscripción
- Utiliza decoradores @lru_cache igual que StudentCycle para optimización.
- Implementa limpieza de caché en el método save() para mantener consistencia de datos.

### Tipos de Actividades y Actividades (ActivityType y Activity)

**En Cayuman**: No existían modelos equivalentes; toda actividad era un workshop.

**En SMileS**:
- `ActivityType` permite definir distintos tipos de actividades (Clases, Almuerzos, Recreos, etc.).
- `Activity` representa actividades específicas que pueden programarse.
- Para emular Cayuman, se debe crear un ActivityType "Class Session" y Activities asociadas a cada SubjectOffering.

### Plantillas de Horarios (ScheduleTemplate y ScheduleAssignment)

**En Cayuman**: No existía un concepto equivalente; los horarios se asociaban directamente a WorkshopPeriods.

**En SMileS**:
- `ScheduleTemplate` define plantillas de horarios que pueden aplicarse a grupos.
- `ScheduleAssignment` mapea franjas horarias a actividades dentro de una plantilla.
- Para emular Cayuman, deben crearse ScheduleTemplates para cada combinación de Group y Term.

### Eventos (EventType y Event)

**En Cayuman**: No existían como modelos separados; los períodos de inscripción eran campos en Period.

**En SMileS**:
- `EventType` define tipos de eventos (Inscripción, Evaluación, etc.).
- `Event` gestiona eventos programados, particularmente períodos de inscripción.
- Para emular Cayuman, deben crearse Events de tipo "Enrollment" basados en los campos enrollment_start/end de Period.
- Implementa métodos como is_current(), is_preview_enabled() e is_enrollment_open() para replicar la funcionalidad de verificación de fechas de Period.

### Servicio de Inscripción (EnrollmentService)

**En Cayuman**: La lógica de inscripción estaba distribuida en varios modelos.

**En SMileS**:
- `EnrollmentService` centraliza la lógica relacionada con inscripciones.
- Implementa métodos como get_available_offerings() y can_enroll().
- Encapsula la lógica que en Cayuman estaba en múltiples modelos y vistas.

## Cómo SMileS Extiende la Funcionalidad de Cayuman

### 1. Sistema de Metadatos Flexible
Todos los modelos principales incluyen campos `metadata` (JSON) que permiten almacenar información adicional sin modificar el esquema de la base de datos. Esto facilita la personalización sin necesidad de migraciones.

### 2. Mejora en el Manejo de Inscripciones
El nuevo modelo Event permite definir varios períodos de inscripción para diferentes grupos o materias, ofreciendo mayor flexibilidad que los campos enrollment_start/end en Period.

### 3. Sistema de Horarios Completo
SMileS implementa un sistema de horarios más robusto, con capacidad para:
- Definir excepciones para días específicos (SpecialDay)
- Crear plantillas de horarios reutilizables (ScheduleTemplate)
- Personalizar horarios individuales (MemberSchedule, MemberScheduleOverride)

### 4. Seguimiento de Asistencia Mejorado
El modelo Attendance permite un registro más detallado incluyendo llegadas tardías, salidas anticipadas y notas específicas, superando las capacidades básicas de Cayuman.

## Proceso de Migración

Para migrar desde Cayuman a SMileS, se siguen estos pasos específicos:

1. **Miembros**: No requiere migración específica ya que se utiliza el mismo modelo.

2. **Ciclos a Grupos**:
   ```python
   # Ejemplo simplificado del proceso de migración
   for cycle in Cycle.objects.all():
       Group.objects.create(
           name=cycle.name,
           group_type="Cycle",
           description=cycle.description,
           is_primary=True
       )
   ```

3. **Períodos a Términos**:
   ```python
   for period in Period.objects.all():
       term = Term.objects.create(
           name=period.name,
           term_type="Workshop Period",
           description=period.description,
           date_start=period.date_start,
           date_end=period.date_end,
           has_enrollment_period=True
       )

       # Migrar datos de inscripción
       if hasattr(period, 'enrollment_start'):
           term.add_enrollment_period(
               name="Regular",
               start_date=period.enrollment_start,
               end_date=period.enrollment_end or (period.enrollment_start + timedelta(days=5))
           )
   ```

4. **Workshops a Subjects**:
   ```python
   # Crear tipo de asignatura para workshops
   workshop_type = SubjectType.objects.create(
       name="Workshop",
       description="Talleres",
       is_selectable=True
   )

   # Migrar cada workshop
   for workshop in Workshop.objects.all():
       Subject.objects.create(
           name=workshop.name,
           type=workshop_type,
           description=workshop.description,
           metadata={'full_name': workshop.full_name}
       )
   ```

5. **WorkshopPeriods a SubjectOfferings**:
   ```python
   for wp in WorkshopPeriod.objects.all():
       # Crear la oferta de asignatura
       offering = SubjectOffering.objects.create(
           subject=Subject.objects.get(name=wp.workshop.name),
           term=Term.objects.get(name=wp.period.name),
           teacher=wp.teacher,
           max_students=wp.max_students
       )

       # Asociar con grupos elegibles (ciclos)
       for cycle in wp.cycles.all():
           group = Group.objects.get(name=cycle.name, group_type="Cycle")
           offering.eligible_groups.add(group)
   ```

6. **Schedules a TimeSlots**:
   ```python
   for schedule in Schedule.objects.all():
       TimeSlot.objects.create(
           name=f"{schedule.get_day_display()} {schedule.time_start}-{schedule.time_end}",
           day_of_week=schedule.day.lower(),
           time_start=schedule.time_start,
           time_end=schedule.time_end
       )
   ```

7. **Eventos de Inscripción**:
   ```python
   # Crear tipo de evento para inscripciones
   enrollment_type = EventType.objects.create(
       name="Enrollment",
       description="Período de inscripción"
   )

   # Crear eventos para cada término
   for term in Term.objects.all():
       enrollment_periods = term.get_enrollment_periods()
       for period in enrollment_periods:
           event = Event.objects.create(
               name=f"Inscripción {term.name}",
               type=enrollment_type,
               term=term,
               preview_date=term.get_preview_date(),
               date_start=period.get('start_date'),
               date_end=period.get('end_date'),
               is_active=True
           )

           # Vincular con grupos aplicables
           for group in Group.objects.filter(group_type="Cycle"):
               event.affects_groups.add(group)
   ```

## Requisitos de Implementación por Modelo

### BaseModel
✅ Implementar created_at y updated_at como campos comunes.

### Member
✅ Mantener propiedades is_student e is_teacher.
✅ Implementar current_student_cycle para obtener asignación de grupo.
✅ Migrar métodos de verificación de inscripción.

### Group (reemplaza Cycle)
✅ Configurar group_type="Cycle" para emular ciclos.
✅ Implementar relaciones jerárquicas si es necesario.

### Term (reemplaza Period)
✅ Implementar métodos para verificar estado (current, past, future).
✅ Añadir soporte para períodos de inscripción flexibles.
✅ Implementar métodos de comprobación de inscripción y preview.

### SubjectType y Subject (reemplazan Workshop)
✅ Crear tipo "Workshop" por defecto.
✅ Migrar datos manteniendo nombres y descripciones.

### SubjectOffering (reemplaza WorkshopPeriod)
✅ Implementar count_classes(), count_students() y remaining_quota().
✅ Vincular con Event para manejar inscripciones.
✅ Mantener relaciones con TimeSlot para horarios.

### TimeSlot (reemplaza Schedule)
✅ Implementar validación de superposición de horarios.
✅ Mantener identificación de día y horas.

### MemberGroupAssignment (reemplaza StudentCycle)
✅ Implementar subject_offerings_by_time_slot() similar a workshop_periods_by_schedule().
✅ Implementar is_schedule_full() para verificar horarios completos.
✅ Utilizar decoradores @lru_cache para optimización.
✅ Implementar limpieza de caché en save().

### Event y EventType (nueva funcionalidad)
✅ Crear tipos de eventos predeterminados: "Enrollment", "Evaluation", etc.
✅ Implementar métodos para verificar estado (current, preview, enrollment).
✅ Vincular eventos con términos y grupos.

### EnrollmentService (nueva funcionalidad)
✅ Centralizar lógica de inscripción de Cayuman.
✅ Implementar get_available_offerings() y can_enroll().
✅ Manejar reglas de negocio para inscripciones.
