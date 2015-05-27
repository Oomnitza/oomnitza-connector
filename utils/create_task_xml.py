import os
import xml.dom.minidom

from utils.relative_path import relative_path


def create_task_xml(period, options):
    try:
        file = relative_path('connector_gui/templates/task_scheduler.xml')

        if not os.path.exists(file):
            return {'result': '', 'error': 'File task_scheduler.xml doesn\'t exist.'}

        dom = xml.dom.minidom.parse(file)
        trig = dom.getElementsByTagName('Triggers')[0]

        start_bound = dom.createElement('StartBoundary')
        start_bound.appendChild(dom.createTextNode(options['start_time']))

        enabled = dom.createElement('Enabled')
        enabled.appendChild(dom.createTextNode('true'))

        author = dom.getElementsByTagName('Author')[0]
        author.appendChild(dom.createTextNode(options['user']))

        user_id = dom.getElementsByTagName('UserId')[0]
        user_id.appendChild(dom.createTextNode(options['user']))

        command = dom.getElementsByTagName('Command')[0]
        command.appendChild(dom.createTextNode(options['command']))

        args = dom.getElementsByTagName('Arguments')[0]
        args.appendChild(dom.createTextNode(options['arguments']))

        if period == 'once':
            time_trig = dom.createElement('TimeTrigger')
            trig.appendChild(time_trig)
            time_trig.appendChild(start_bound)
            time_trig.appendChild(enabled)

        elif period == 'daily':
            cal_trig = dom.createElement('CalendarTrigger')
            trig.appendChild(cal_trig)
            cal_trig.appendChild(start_bound)
            cal_trig.appendChild(enabled)

            sched_day = dom.createElement('ScheduleByDay')
            days_inter = dom.createElement('DaysInterval')
            days_inter.appendChild(dom.createTextNode(options['recur']))
            sched_day.appendChild(days_inter)
            cal_trig.appendChild(sched_day)

        elif period == 'weekly':
            cal_trig = dom.createElement('CalendarTrigger')
            trig.appendChild(cal_trig)
            cal_trig.appendChild(start_bound)
            cal_trig.appendChild(enabled)

            sched_week = dom.createElement('ScheduleByWeek')
            days_week = dom.createElement('DaysOfWeek')
            for day in options['days']:
                days_week.appendChild(dom.createElement(day))
            weeks_inter = dom.createElement('WeeksInterval')
            weeks_inter.appendChild(dom.createTextNode(options['recur']))
            sched_week.appendChild(days_week)
            sched_week.appendChild(weeks_inter)
            cal_trig.appendChild(sched_week)

        elif period == 'monthly':
            cal_trig = dom.createElement('CalendarTrigger')
            trig.appendChild(cal_trig)
            cal_trig.appendChild(start_bound)
            cal_trig.appendChild(enabled)

            sched_month = dom.createElement('ScheduleByMonth')
            days_month = dom.createElement('DaysOfMonth')
            for day in options['days']:
                day_elem = dom.createElement('Day')
                day_elem.appendChild(dom.createTextNode(day))
                days_month.appendChild(day_elem)
            sched_month.appendChild(days_month)

            months = dom.createElement('Months')
            for month in options['months']:
                months.appendChild(dom.createElement(month))
            sched_month.appendChild(months)
            cal_trig.appendChild(sched_month)

        temp_xml_path = relative_path('temp.xml')

        with open(temp_xml_path, 'w') as xml_file:
            xml_file.write(dom.toxml())
            return temp_xml_path

    except Exception as exp:
        return {'result': '', 'error': str(exp)}