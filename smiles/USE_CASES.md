# Casos de Uso de SMileS

Este documento presenta diferentes escenarios y tipos de instituciones educativas que podrían beneficiarse del sistema SMileS, explicando cómo cada una modelaría su estructura y procesos utilizando las características flexibles del sistema.

## Índice

1. [Escuela Tradicional](#escuela-tradicional)
2. [Escuela Montessori](#escuela-montessori)
3. [Escuela de Artes](#escuela-de-artes)
4. [Centro de Educación Técnica](#centro-de-educación-técnica)
5. [Comunidad de Homeschooling](#comunidad-de-homeschooling)
6. [Caso Especial: Hogwarts](#caso-especial-hogwarts)

## Escuela Tradicional

### Perfil
**Colegio San Patricio**: Escuela primaria y secundaria con estructura de grados tradicionales y asignaturas fijas por nivel.

### Configuración en SMileS

#### Grupos
- **Tipos de grupo**: "Grado" (group_type="Grado", is_primary=true)
- **Grupos concretos**:
  - "1° Básico" (group_type="Grado")
  - "2° Básico" (group_type="Grado")
  - Hasta "4° Medio" (group_type="Grado")

#### Términos
- **Tipos de término**: "Año Escolar", "Semestre"
- **Términos concretos**:
  - "Año Escolar 2024" (term_type="Año Escolar", date_start="2024-03-01", date_end="2024-12-15")
  - "Primer Semestre 2024" (term_type="Semestre", date_start="2024-03-01", date_end="2024-07-15")
  - "Segundo Semestre 2024" (term_type="Semestre", date_start="2024-07-16", date_end="2024-12-15")

#### Asignaturas
- **Tipos de asignatura**: "Asignatura Académica" (is_selectable=false), "Taller Optativo" (is_selectable=true)
- **Asignaturas concretas**:
  - "Matemáticas" (type="Asignatura Académica")
  - "Lenguaje" (type="Asignatura Académica")
  - "Música" (type="Taller Optativo")
  - "Teatro" (type="Taller Optativo")

#### Inscripciones
- Las asignaturas académicas se asignan automáticamente según el grado
- Los talleres optativos utilizan `enrollment_start` y `enrollment_end` específicos
- Se establecen cuotas para talleres usando `max_students`

#### Horarios
- Plantillas fijas por grado usando `ScheduleTemplate`
- Bloques de 45 minutos definidos como `TimeSlot`
- Recreos y almuerzos como `Activity` con tipos específicos

## Escuela Montessori

### Perfil
**Jardín Montessori Las Encinas**: Educación basada en ambientes preparados y grupos de edades mixtas.

### Configuración en SMileS

#### Grupos
- **Tipos de grupo**: "Comunidad" (group_type="Comunidad", is_primary=true)
- **Grupos concretos**:
  - "Nido (0-3 años)" (group_type="Comunidad")
  - "Casa de Niños (3-6 años)" (group_type="Comunidad")
  - "Taller I (6-9 años)" (group_type="Comunidad")
  - "Taller II (9-12 años)" (group_type="Comunidad")

#### Términos
- **Tipos de término**: "Ciclo Montessori" (term_type="Ciclo Montessori")
- **Términos concretos**:
  - "Ciclo 2024-2025" (term_type="Ciclo Montessori", date_start="2024-03-01", date_end="2025-02-28")

#### Asignaturas
- **Tipos de asignatura**: "Área Montessori" (is_selectable=false)
- **Asignaturas concretas**:
  - "Vida Práctica" (type="Área Montessori")
  - "Sensorial" (type="Área Montessori")
  - "Lenguaje" (type="Área Montessori")
  - "Matemáticas" (type="Área Montessori")
  - "Cultura" (type="Área Montessori")

#### Inscripciones
- No hay inscripciones a áreas específicas (is_selectable=false)
- Los estudiantes trabajan en todas las áreas según su desarrollo

#### Horarios
- Bloques de trabajo ininterrumpidos de 3 horas (`TimeSlot` largos)
- Actividades registradas posteriores a la elección del estudiante
- El modelo `Attendance` registra qué áreas utilizó cada estudiante

## Escuela de Artes

### Perfil
**Conservatorio Nacional**: Escuela de música con estructura por niveles de habilidad y especialidades instrumentales.

### Configuración en SMileS

#### Grupos
- **Tipos de grupo**:
  - "Nivel" (group_type="Nivel", is_primary=true)
  - "Especialidad" (group_type="Especialidad", is_primary=true)
- **Grupos concretos**:
  - "Nivel Básico", "Nivel Intermedio", "Nivel Avanzado" (group_type="Nivel")
  - "Piano", "Violín", "Flauta Traversa", etc. (group_type="Especialidad")

#### Términos
- **Tipos de término**: "Año Académico", "Recital"
- **Términos concretos**:
  - "Año Académico 2024" (term_type="Año Académico")
  - "Recital Semestral Junio 2024" (term_type="Recital")
  - "Recital de Fin de Año 2024" (term_type="Recital")

#### Asignaturas
- **Tipos de asignatura**:
  - "Instrumento Principal" (is_selectable=false)
  - "Teoría Musical" (is_selectable=false)
  - "Ensamble" (is_selectable=true)
- **Asignaturas concretas**:
  - "Clases de Piano" (type="Instrumento Principal")
  - "Teoría Musical I, II, III" (type="Teoría Musical")
  - "Ensamble de Cuerdas", "Orquesta", "Grupo de Cámara" (type="Ensamble")

#### Inscripciones
- La inscripción en instrumento principal es automática según especialidad
- Los ensambles tienen inscripción abierta con `enrollment_start` y `enrollment_end`
- Se requiere aprobación del profesor (almacenada en `metadata`)

#### Horarios
- Clases individuales programadas mediante `MemberSchedule` personalizado
- Clases grupales como teoría con `ScheduleTemplate` fijo
- Ensayos de ensambles en horarios variables con `SpecialDay`

## Centro de Educación Técnica

### Perfil
**Instituto Técnico Profesional**: Formación en carreras técnicas con módulos prácticos y teóricos.

### Configuración en SMileS

#### Grupos
- **Tipos de grupo**:
  - "Carrera" (group_type="Carrera", is_primary=true)
  - "Nivel" (group_type="Nivel", is_primary=true)
- **Grupos concretos**:
  - "Técnico en Enfermería", "Técnico en Electricidad" (group_type="Carrera")
  - "Primer Año", "Segundo Año" (group_type="Nivel")

#### Términos
- **Tipos de término**: "Semestre", "Práctica Profesional"
- **Términos concretos**:
  - "Primer Semestre 2024" (term_type="Semestre")
  - "Segundo Semestre 2024" (term_type="Semestre")
  - "Práctica Profesional Verano 2024" (term_type="Práctica Profesional")

#### Asignaturas
- **Tipos de asignatura**:
  - "Módulo Teórico" (is_selectable=false)
  - "Laboratorio" (is_selectable=false)
  - "Electivo" (is_selectable=true)
- **Asignaturas concretas**:
  - "Anatomía", "Circuitos Eléctricos" (type="Módulo Teórico")
  - "Laboratorio de Enfermería", "Taller de Instalaciones" (type="Laboratorio")
  - "Inglés Técnico", "Emprendimiento" (type="Electivo")

#### Inscripciones
- Módulos obligatorios asignados automáticamente según carrera y nivel
- Electivos con períodos de inscripción controlados
- Prácticas profesionales con proceso de asignación (en `metadata`)

#### Horarios
- Bloques combinados de teoría y práctica en el mismo día
- Rotaciones de laboratorio con grupos pequeños (`MemberScheduleOverride`)
- Períodos de práctica profesional como `SpecialDay` extensos

## Comunidad de Homeschooling

### Perfil
**Comunidad Educativa Libre**: Grupo de familias que comparten recursos y actividades educativas.

### Configuración en SMileS

#### Grupos
- **Tipos de grupo**:
  - "Familia" (group_type="Familia", is_primary=true)
  - "Grupo de Interés" (group_type="Grupo de Interés", is_primary=false)
- **Grupos concretos**:
  - "Familia Rodríguez", "Familia Pérez", etc. (group_type="Familia")
  - "Club de Ciencias", "Grupo de Literatura", etc. (group_type="Grupo de Interés")

#### Términos
- **Tipos de término**: "Temporada", "Proyecto"
- **Términos concretos**:
  - "Temporada Otoño-Invierno 2024" (term_type="Temporada")
  - "Proyecto Huerto Comunitario" (term_type="Proyecto", date_start="2024-04-01", date_end="2024-07-30")

#### Asignaturas
- **Tipos de asignatura**:
  - "Encuentro Comunitario" (is_selectable=true)
  - "Taller Familiar" (is_selectable=true)
  - "Mentor Especializado" (is_selectable=true)
- **Asignaturas concretas**:
  - "Círculo de Matemáticas" (type="Encuentro Comunitario")
  - "Taller de Arte en Familia" (type="Taller Familiar")
  - "Clases de Música con Profesor Miguel" (type="Mentor Especializado")

#### Inscripciones
- Todos los encuentros son opcionales (is_selectable=true)
- Períodos de inscripción flexibles con días de antelación
- Contribuciones económicas registradas en `metadata`

#### Horarios
- Horarios flexibles definidos semanalmente o mensualmente
- Actividades en diferentes ubicaciones (casas, parques, etc.)
- Sistema de notificaciones para cambios de último momento

## Caso Especial: Hogwarts

### Perfil
**Colegio Hogwarts de Magia y Hechicería**: Escuela internado de magia con un sistema de casas y cursos especializados en artes mágicas.

### Configuración en SMileS

#### Grupos
- **Tipos de grupo**:
  - "Casa" (group_type="Casa", is_primary=true)
  - "Año" (group_type="Año", is_primary=true)
  - "Equipo de Quidditch" (group_type="Equipo", is_primary=false)
- **Grupos concretos**:
  - "Gryffindor", "Hufflepuff", "Ravenclaw", "Slytherin" (group_type="Casa")
  - "Primer Año", "Segundo Año", ... "Séptimo Año" (group_type="Año")
  - "Equipo Gryffindor", "Equipo Slytherin", etc. (group_type="Equipo")

#### Términos
- **Tipos de término**: "Año Escolar", "Trimestre"
- **Términos concretos**:
  - "Año Escolar 1991-1992" (term_type="Año Escolar", date_start="1991-09-01", date_end="1992-06-30")
  - "Primer Trimestre 1991" (term_type="Trimestre", date_start="1991-09-01", date_end="1991-12-20")
  - "Torneo de los Tres Magos" (term_type="Especial", date_start="1994-10-30", date_end="1995-06-24")

#### Asignaturas
- **Tipos de asignatura**:
  - "Asignatura Obligatoria" (is_selectable=false)
  - "Asignatura Electiva" (is_selectable=true)
  - "Actividad Extracurricular" (is_selectable=true)
- **Asignaturas concretas**:
  - "Transformaciones", "Encantamientos", "Pociones", "Defensa Contra las Artes Oscuras" (type="Asignatura Obligatoria")
  - "Adivinación", "Estudio de Runas Antiguas", "Cuidado de Criaturas Mágicas" (type="Asignatura Electiva", disponible desde 3er año)
  - "Práctica de Quidditch", "Club de Duelo" (type="Actividad Extracurricular")

#### Inscripciones
- Asignaturas obligatorias según año
- Electivas seleccionables desde tercer año:
  ```python
  # Ejemplo de lógica en el servicio EnrollmentService
  if student.get_group(group_type="Año").name in ["Tercer Año", "Cuarto Año", "Quinto Año", "Sexto Año", "Séptimo Año"]:
      # Permitir inscripción en electivas
  ```
- Pruebas de selección para equipos de Quidditch (almacenadas como eventos en `SpecialDay`)

#### Horarios
- Horarios diferentes según casa y año
- Clases comunes entre casas (ej. Gryffindor y Slytherin en Pociones)
- Horarios nocturnos para Astronomía
- Prácticas de Quidditch según disponibilidad del campo

#### Características especiales
- La escalera cambiante requiere `MemberScheduleOverride` frecuentes
- El sistema del Cáliz de Fuego para el Torneo de los Tres Magos como proceso de inscripción especial
- Ceremonia del Sombrero Seleccionador como asignación inicial de casas
- El mapa del merodeador como visualización del horario en tiempo real

#### Ejemplo de datos

```python
# Creación de casas
gryffindor = Group.objects.create(
    name="Gryffindor",
    group_type="Casa",
    is_primary=True,
    metadata={
        "founder": "Godric Gryffindor",
        "colors": ["Escarlata", "Dorado"],
        "animal": "León",
        "ghost": "Sir Nicholas Casi Decapitado",
        "common_room_location": "Torre Gryffindor, séptimo piso",
        "password": "Cambia semanalmente"  # Solo visible para miembros y personal
    }
)

# Creación de asignatura
defense = Subject.objects.create(
    name="Defensa Contra las Artes Oscuras",
    type=SubjectType.objects.get(name="Asignatura Obligatoria"),
    description="Estudio de técnicas defensivas contra magia oscura y criaturas peligrosas",
    metadata={
        "classroom": "Aula 3C",
        "textbook": "Las Fuerzas Oscuras: Una Guía para la Autoprotección",
        "previous_professors": ["Quirrell", "Lockhart", "Lupin", "Moody (Barty Crouch Jr.)", "Umbridge", "Snape"]
    }
)

# Oferta de asignatura para un término y profesor específico
defense_offering = SubjectOffering.objects.create(
    subject=defense,
    term=Term.objects.get(name="Año Escolar 1995-1996"),
    teacher=Member.objects.get(user__username="d.umbridge"),
    max_students=30,
    metadata={
        "decree_number": "Decreto de Enseñanza nº 26",
        "ministry_approved": True,
        "theoretical_only": True,  # Umbridge solo enseñaba teoría
        "classroom_rules": ["No hablar sin permiso", "Leer el libro de texto", "No practicar hechizos"]
    }
)
defense_offering.eligible_groups.add(Group.objects.get(name="Quinto Año"))

# Evento especial: Club de Duelo
dueling_club = SpecialDay.objects.create(
    name="Reunión del Club de Duelo",
    date=datetime.date(1992, 12, 17),
    is_school_closed=False,
    metadata={
        "location": "Gran Comedor",
        "instructor": "Gilderoy Lockhart, Severus Snape",
        "participants": "Todos los estudiantes",
        "notable_events": "Duelo entre Harry Potter y Draco Malfoy"
    }
)

# Creación de la actividad para el Torneo de los Tres Magos
tournament_activity = Activity.objects.create(
    name="Primera Prueba: Dragones",
    type=ActivityType.objects.get(name="Evento de Torneo"),
    description="Los campeones deben enfrentarse a dragones para obtener un huevo de oro",
    metadata={
        "location": "Arena especial",
        "dragons": ["Colacuerno Húngaro", "Galés Verde", "Hocicorto Sueco", "Bola de Fuego Chino"],
        "spectators": True,
        "safety_measures": "Cuidadores de dragones de reserva, medimagos en espera"
    }
)
```

## Conclusión

El sistema SMileS permite modelar una amplia variedad de instituciones educativas gracias a su enfoque flexible basado en:

1. **Tipos configurables**: Cada escuela define sus propios tipos de grupos, términos y asignaturas
2. **Metadatos extensibles**: Campos JSON permiten almacenar información específica sin cambiar el modelo
3. **Relaciones flexibles**: Las asociaciones entre entidades se pueden adaptar a diferentes estructuras
4. **Control granular de inscripciones**: Desde asignación automática hasta procesos complejos de selección
5. **Gestión avanzada de horarios**: Desde horarios fijos hasta sistemas completamente personalizados

Esta flexibilidad permite que SMileS se adapte a instituciones educativas tanto convencionales como alternativas, e incluso a organizaciones educativas completamente ficticias como Hogwarts.
