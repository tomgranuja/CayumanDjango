from functools import lru_cache

from django.template import Context
from django.template import Library
from django.template import Node
from django.template import Template
from django.template import TemplateSyntaxError
from django.template import Variable
from django.template.base import token_kwargs
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from jinja2 import nodes
from jinja2 import Template as JinjaTemplate
from jinja2.ext import Extension
from jinja2.ext import Markup

# from jinja2 import pass_context

register = Library()


BLOCK_TPL = """
{% for block in blocks %}
<tr{% if tr_class %} class="{{tr_class}}"{% endif %}>
    <th{% if th_class %} class="{{th_class}}"{% endif %} scope="row">{{ block.0.strftime('%H:%M') }} - {{ block.1.strftime('%H:%M') }}</th>

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
            <br /><small>{{workshop_period.teacher.get_full_name()}}</small>
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
        raise TemplateSyntaxError("'timetable' statements should have at least two words: %s" % token.contents)

    workshop_periods = bits[1]
    kwargs = {}
    if len(bits) >= 3:
        remaining_bits = bits[2:]
        kwargs = token_kwargs(remaining_bits, parser, support_legacy=True)
        if not kwargs:
            raise TemplateSyntaxError("%r expected at least one variable assignment" % bits[0])
    if remaining_bits:
        raise TemplateSyntaxError("%r received an invalid token: %r" % (bits[0], remaining_bits[0]))
    nodelist = parser.parse(("endtimetable",))
    parser.delete_first_token()
    return TimetableNode(workshop_periods, nodelist, **kwargs)


class TimetableNode(Node):
    def __init__(self, nodelist, kwargs):
        self.nodelist = nodelist
        self.kwargs = kwargs

    def _render_block(self, context_dict):
        return django_render_string(BLOCK_TPL, context_dict)

    def render(self, context):
        workshop_periods = Variable("workshop_periods").resolve(context)
        days, blocks, schedules = get_scheduling_data()

        results = {}

        for block in blocks:
            for schedule in schedules:
                if schedule.time_start == block[0]:
                    if schedule.id not in results:
                        results[f"{schedule.id}"] = []

                    for workshop_period in workshop_periods:
                        # Update the context with these specific variables for this iteration
                        context.push()
                        context["schedule"] = schedule
                        context["workshop_period"] = workshop_period
                        context.update(self.kwargs)

                        # Render the template block with the updated context
                        rendered_content = self.nodelist.render(context)
                        results[f"{schedule.id}"].append(mark_safe(rendered_content))

                        # Pop the context to avoid side-effects
                        context.pop()

        for key, val in results.items():
            results[key] = "".join(val)

        params = {"tbody": self._render_block({"results": results, "blocks": blocks, "schedules": schedules}), "days": days}
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
        return Markup(jinja2_render_string(BLOCK_TPL, context_dict))

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
