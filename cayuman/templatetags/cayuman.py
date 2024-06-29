from functools import lru_cache

import jinja2
from django.template import Context
from django.template import Library
from django.template import Node
from django.template import Template
from django.template import TemplateSyntaxError
from django.template.base import kwarg_re
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.safestring import SafeString
from django_jinja import library
from jinja2 import nodes
from jinja2 import Template as JinjaTemplate
from jinja2.ext import Extension
from jinja2.ext import Markup

register = Library()


BLOCK_TPL_JINJA2 = """
{% for block in blocks %}
<tr{% if tr_class %} class="{{tr_class}}"{% endif %}>
    <th{% if th_class %} class="{{th_class}}"{% endif %} scope="row">
        {{ block.0.strftime('%H:%M') }} - {{ block.1.strftime('%H:%M') }}
    </th>

    {% for schedule in schedules %}
        {% if schedule.time_start == block.0 %}
            {% if results[schedule.id|string] %}
            <td{% if td_class %} class="{{td_class}}"{% endif %}>
                {{results[schedule.id|string]}}
            </td>
            {% else %}
            <td></td>
            {% endif %}
        {% endif %}
    {% endfor %}
</tr>
{% endfor %}"""


BLOCK_TPL_DJANGO = """
{% for block in blocks %}
<tr{% if tr_class %} class="{{tr_class}}"{% endif %}>
    <th{% if th_class %} class="{{th_class}}"{% endif %} scope="row">
        {{ block.0|date:'H:i' }} - {{ block.1|date:'H:i' }}
    </th>

    {% for schedule in schedules %}
        {% if schedule.time_start == block.0 %}
            {% with key=schedule.id|stringformat:"d" %}
                {% if key in results %}
                    {% for k, v in results.items %}
                        {# TO-DO: make more efficient #}
                        {% if k == key %}
                        <td{% if td_class %} class="{{td_class}}"{% endif %}>
                            {{v|default:''}}
                        </td>
                        {% endif %}
                    {% endfor %}
                {% else %}
                    <td></td>
                {% endif %}
            {% endwith %}
        {% endif %}
    {% endfor %}
</tr>
{% endfor %}"""


@lru_cache
def get_scheduling_data():
    from cayuman.models import Schedule

    schedules = Schedule.objects.ordered()
    days = [t for t in Schedule.CHOICES]
    raw_blocks = [(block.time_start, block.time_end) for block in schedules]
    blocks = []
    [blocks.append(item) for item in raw_blocks if item not in blocks]

    return days, blocks, schedules


def django_render_string(template_string, context_dict):
    # Create a Template object
    template = Template(template_string)

    # Create a Context object
    context = Context(context_dict)

    # Render the template with the context
    return template.render(context)


def jinja2_render_string(template_string, context_dict):
    # Create a Template object
    template = JinjaTemplate(template_string)

    # Render the template with the context dictionary
    return template.render(context_dict)


@register.tag("timetable")
def do_timetable(parser, token):
    """
    Loop over each item in a workshop_periods list and render it as a timetable

    {% timetable workshop_periods key1=var1 key2=var2 ... keyN=varN %}
        {% if schedule in workshop_period.schedules.all() %}
            <a href="{{ url('workshop_period', workshop_period_id=workshop_period.id) }}">{{workshop_period.workshop.name}}</a>
            <br /><small>{{workshop_period.teacher.get_full_name}}</small>
        {% endif %}
    {% endtimetable %}

    The content of the `timetable` block will be rendered for each item in the `workshop_periods` list.

        ==========================  ================================================
        Variable                    Description
        ==========================  ================================================
        ``workshop_period``         Current `workshop_period` object
        ``key``                     Pass keyword args to the template
        ==========================  ================================================
    """
    bits = token.split_contents()
    if len(bits) < 2:
        raise TemplateSyntaxError("`timetable` statements should have at least two words: %s" % token.contents)

    workshop_periods = parser.compile_filter(bits[1])

    if len(bits) >= 3:
        kwargs = {}
        bits = bits[2:]

        for bit in bits:
            match = kwarg_re.match(bit)
            if not match:
                raise TemplateSyntaxError("Malformed arguments for `timetable` statement")
            name, value = match.groups()
            if name:
                kwargs[name] = parser.compile_filter(value)
            else:
                raise TemplateSyntaxError("Malformed arguments for `timetable` statement")

    nodelist = parser.parse(("endtimetable",))
    parser.delete_first_token()

    return TimetableNode(workshop_periods, nodelist, **kwargs)


class TimetableNode(Node):
    """Django Templating templatetag to easily display timetables"""

    def __init__(self, workshop_periods, nodelist, **kwargs):
        self.workshop_periods = workshop_periods
        self.nodelist = nodelist
        self.kwargs = kwargs

    def render(self, context):
        workshop_periods = self.workshop_periods.resolve(context)
        kwargs = {k: v.resolve(context) for k, v in self.kwargs.items()}
        days, blocks, schedules = get_scheduling_data()

        results = {}

        for block in blocks:
            for schedule in schedules:
                if schedule.time_start == block[0]:
                    if schedule.id not in results:
                        results[f"{schedule.id}"] = []
                    for workshop_period in workshop_periods:
                        # Manually update the context for each iteration
                        temp_ctx = {"schedule": schedule, "workshop_period": workshop_period}
                        with context.push(**temp_ctx):
                            rendered_content = self.nodelist.render(context)
                            if rendered_content.strip():
                                results[f"{schedule.id}"].append(mark_safe(rendered_content.strip()))
                            else:
                                results[f"{schedule.id}"].append("")

        for key, val in results.items():
            if any(isinstance(v, SafeString) for v in val):
                results[key] = mark_safe("".join([v.strip() for v in val]))
            else:
                results[key] = None

        params_tbody = {"results": results, "blocks": blocks, "schedules": schedules}
        params_tbody.update(kwargs)
        params = {"tbody": django_render_string(BLOCK_TPL_DJANGO, params_tbody), "days": days}
        params.update(kwargs)
        return render_to_string("timetable_template.html", params)


class TimetableExtension(Extension):
    """Jinja2 Extension to easily display a timetable"""

    tags = {"timetable"}

    def parse(self, parser):
        lineno = next(parser.stream).lineno

        workshop_periods = parser.parse_expression()

        kwargs = []
        while parser.stream.current.type != "block_end":
            parser.stream.expect("comma")
            target = parser.parse_assign_target()
            target.set_ctx("param")

            parser.stream.expect("assign")
            value = parser.parse_expression()

            pair = nodes.Keyword()
            pair.key = target.name
            pair.value = value
            kwargs.append(pair)

        body = parser.parse_statements(["name:endtimetable"], drop_needle=True)

        wp = nodes.Name()
        wp.name = "workshop_period"
        wp.ctx = "param"

        sc = nodes.Name()
        sc.name = "schedule"
        sc.ctx = "param"

        return nodes.CallBlock(self.call_method("_render_timetable", [workshop_periods], kwargs), [wp, sc], [], body).set_lineno(lineno)

    def _render_block(self, context_dict):
        return Markup(jinja2_render_string(BLOCK_TPL_JINJA2, context_dict))

    def _render_template(self, template_path, context):
        # Load and render the template with the given context
        template = self.environment.get_template(template_path)
        return Markup(template.render(context))

    def _render_timetable(self, workshop_periods, **kwargs):
        results = {}
        days, blocks, schedules = get_scheduling_data()
        caller = kwargs.pop("caller")

        for block in blocks:
            for schedule in schedules:
                if schedule.time_start == block[0]:
                    if schedule.id not in results:
                        results[f"{schedule.id}"] = []
                    for workshop_period in workshop_periods:
                        # Manually update the context for each iteration
                        temp_context = {"schedule": schedule, "workshop_period": workshop_period}

                        # Call the body of the block with the updated context
                        rendered_content = caller(**temp_context)
                        if rendered_content.strip():
                            results[f"{schedule.id}"].append(Markup(rendered_content.strip()))
                        else:
                            results[f"{schedule.id}"].append("")

        for key, val in results.items():
            if any(isinstance(v, Markup) for v in val):
                results[key] = Markup("".join(val))
            else:
                results[key] = None

        params_tbody = {"results": results, "blocks": blocks, "schedules": schedules}
        params_tbody.update(kwargs)
        params = {"tbody": self._render_block(params_tbody), "days": days}
        params.update(kwargs)
        return self._render_template("timetable_template.html", params)


@library.global_function
@jinja2.pass_context
def url_switch_period(context, period_id: int):
    """Simple jinja2 filters that transforms any url to the same one but switched to the given period"""
    from django.urls import reverse, resolve
    from django.urls.exceptions import NoReverseMatch

    request = context.get("request")

    # Get the current URL path and its resolver match
    match = resolve(request.path_info)

    # Prepare new kwargs for URL reversing
    new_kwargs = {**match.kwargs, "period_id": period_id}

    # Create the new URL
    try:
        new_url = reverse(match.view_name, args=match.args, kwargs=new_kwargs)
    except NoReverseMatch:
        # if url does not use period_id kwarg then just return the same url
        new_url = reverse(match.view_name, kwargs=match.kwargs)
    return new_url
