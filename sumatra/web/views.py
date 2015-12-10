"""
Defines views for the Sumatra web interface.

:copyright: Copyright 2006-2015 by the Sumatra team, see doc/authors.txt
:license: BSD 2-clause, see LICENSE for details.
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from builtins import str

import parameters
import mimetypes
from django.conf import settings as django_settings
from django.http import HttpResponse, Http404
from django.shortcuts import render_to_response
from django.views.generic.list import ListView
try:
    from django.views.generic.dates import MonthArchiveView
except ImportError:  # older versions of Django
    MonthArchiveView = object

import json
import os
from django.views.generic import View, DetailView
from django.db.models import Q
from tagging.models import Tag
from sumatra.recordstore.serialization import datestring_to_datetime
from sumatra.recordstore.django_store.models import Project, Record, DataKey, Datastore
from sumatra.records import RecordDifference
from sumatra.versioncontrol import get_working_copy

DEFAULT_MAX_DISPLAY_LENGTH = 10 * 1024
global_conf_file = os.path.expanduser(os.path.join("~", ".smtrc"))
mimetypes.init()

_label_db = django_settings.LABEL_DB


class ProjectListView(ListView):
    model = Project
    context_object_name = 'projects'
    template_name = 'project_list.html'

    def get_queryset(self):
        projects = []
        for db in django_settings.DATABASES.keys():
            projects.extend(Project.objects.using(db).all())
        return projects


class ProjectDetailView(DetailView):
    context_object_name = 'project'
    template_name = 'project_detail.html'

    def get_object(self):
        return Project.objects.using(_label_db.get(self.kwargs["project"],'default')).get(pk=self.kwargs["project"])

    def get_context_data(self, **kwargs):
        context = super(ProjectDetailView, self).get_context_data(**kwargs)
        context['read_only'] = django_settings.READ_ONLY
        return context

    def get_context_data(self, **kwargs):
        context = super(ProjectDetailView, self).get_context_data(**kwargs)
        context['read_only'] = django_settings.READ_ONLY
        return context

    def post(self, request, *args, **kwargs):
        if django_settings.READ_ONLY:
            return HttpResponse('It is in read-only mode.')
        name = request.POST.get('name', None)
        description = request.POST.get('description', None)
        project = self.get_object()
        if description is not None:
            project.description = description
            project.save()
        if name is not None:
            project.name = name
            project.save()
        return HttpResponse('OK')


class RecordListView(ListView):
    context_object_name = 'project'
    template_name = 'record_list.html'

    def get_queryset(self):
        return Project.objects.using(_label_db.get(self.kwargs["project"],'default')).get(pk=self.kwargs["project"])

    def get_context_data(self, **kwargs):
        context = super(RecordListView, self).get_context_data(**kwargs)
        context['tags'] = Tag.objects.using(_label_db.get(self.kwargs["project"],'default')).all()  # would be better to filter, to return only tags used in this project.
        context['read_only'] = django_settings.READ_ONLY
        return context

def unescape(label):
    return label.replace("||", "/")


class RecordDetailView(DetailView):
    context_object_name = 'record'
    template_name = 'record_detail.html'

    def get_object(self):
        label = unescape(self.kwargs["label"])
        return Record.objects.using(_label_db.get(self.kwargs["project"],'default')).get(label=label, project__id=self.kwargs["project"])

    def get_context_data(self, **kwargs):
        context = super(RecordDetailView, self).get_context_data(**kwargs)
        context['project'] = Project.objects.using(_label_db.get(self.kwargs["project"],'default')).get(pk=self.kwargs["project"])
        context['project_name'] = self.kwargs["project"]  # use project full name?
        parameter_set = self.object.parameters.to_sumatra()
        if hasattr(parameter_set, "as_dict"):
            parameter_set = parameter_set.as_dict()
        context['parameters'] = parameter_set
        context['read_only'] = django_settings.READ_ONLY
        return context

    def post(self, request, *args, **kwargs):
        if django_settings.READ_ONLY:
            return HttpResponse('It is in read-only mode.')
        record = self.get_object()
        for attr in ("reason", "outcome", "tags"):
            value = request.POST.get(attr, None)
            if value is not None:
                setattr(record, attr, value)
        record.save()
        return HttpResponse('OK')


class DataListView(ListView):
    context_object_name = 'project'
    template_name = 'data_list.html'

    def get_queryset(self):
        return Project.objects \
            .using(_label_db.get(self.kwargs["project"],'default')) \
            .get(pk=self.kwargs["project"])

    def get_context_data(self, **kwargs):
        context = super(DataListView, self).get_context_data(**kwargs)
        return context


class DataDetailView(DetailView):
    context_object_name = 'data_key'

    def get_object(self):
        attrs = dict(path=self.request.GET['path'],
                     digest=self.request.GET['digest'],
                     creation=datestring_to_datetime(self.request.GET['creation']))
        return DataKey.objects.using(_label_db.get(self.kwargs["project"],'default')).get(**attrs)

    def get_context_data(self, **kwargs):
        context = super(DataDetailView, self).get_context_data(**kwargs)
        context['project'] = Project.objects.using(_label_db.get(self.kwargs["project"],'default')).get(pk=self.kwargs["project"])
        context['project_name'] = self.kwargs["project"]  # use project full name?

        if 'truncate' in self.request.GET:
            if self.request.GET['truncate'].lower() == 'false':
                max_display_length = None
            else:
                max_display_length = int(self.request.GET['truncate']) * 1024
        else:
            max_display_length = DEFAULT_MAX_DISPLAY_LENGTH

        datakey = self.object
        context['data_key'] = datakey
        mimetype = datakey.to_sumatra().metadata["mimetype"]
        try:
            datastore = datakey.output_from_record.datastore
        except AttributeError:
            datastore = datakey.input_to_records.first().input_datastore
        context['datastore_id'] = datastore.pk

        content_dispatch = {
            "text/csv": self.handle_csv,
            "text/plain": self.handle_plain_text,
            "application/zip": self.handle_zipfile
        }
        if mimetype in content_dispatch:
            content = datastore.to_sumatra().get_content(datakey.to_sumatra(),
                                                         max_length=max_display_length)
            context['truncated'] = (max_display_length is not None
                                    and len(content) >= max_display_length)

            context = content_dispatch[mimetype](context, content)
        return context

    def handle_csv(self, context, content):
        import csv
        content = content.rpartition('\n')[0]
        lines = content.splitlines()
        context['reader'] = csv.reader(lines)
        return context

    def handle_plain_text(self, context, content):
        context["content"] = content
        if os.path.exists('.smt/templates'):
            context["templates"] = [os.path.splitext(t)[0] for t in os.listdir(os.getcwd()+'/.smt/templates') if t.endswith('.html')]
            context["templates"].sort()
        return context

    def handle_zipfile(self, context, content):
        import zipfile
        if zipfile.is_zipfile(path):
            zf = zipfile.ZipFile(path, 'r')
            contents = zf.namelist()
            zf.close()
        context["content"] = "\n".join(contents)

    def get_template_names(self):
        datakey = self.object.to_sumatra()
        mimetype = datakey.metadata["mimetype"]
        mimetype_guess, encoding = mimetypes.guess_type(datakey.path)

        if encoding == 'gzip':
            raise NotImplementedError("to be reimplemented")

        template_dispatch = {
            "image/png": 'data_detail_image.html',
            "image/jpeg": 'data_detail_image.html',
            "image/gif": 'data_detail_image.html',
            "image/x-png": 'data_detail_image.html',
            "text/csv": 'data_detail_csv.html',
            "text/plain": 'data_detail_text.html',
            "application/zip": 'data_detail_zip.html'
        }
        template_name = template_dispatch.get(mimetype, 'data_detail_base.html')
        return template_name


class ImageListView(ListView):
    context_object_name = 'project'
    template_name = 'image_list.html'

    def get_queryset(self):
        return Project.objects \
            .using(_label_db.get(self.kwargs["project"],'default')) \
            .get(pk=self.kwargs["project"])

        return DataKey.objects \
            .using(_label_db.get(self.kwargs["project"],'default')) \
            .filter(output_from_record__project_id=self.kwargs["project"]) \
            .filter(metadata__contains='image')

    def get_context_data(self, **kwargs):
        context = super(ImageListView, self).get_context_data(**kwargs)
        context['project'] = Project.objects.using(_label_db.get(self.kwargs["project"],'default')).get(pk=self.kwargs["project"])
        context['tags'] = Tag.objects.using(_label_db.get(self.kwargs["project"],'default')).all()  # would be better to filter, to return only tags used in this project.
        return context


def datatable_record(request, project):
    columns = ['label', 'timestamp', 'reason', 'outcome', 'input_data', 'output_data',
     'duration', 'launch_mode', 'executable', 'main_file', 'version', 'script_arguments', 'tags']
    selected_tag = request.GET['tag']
    search_value = request.GET['search[value]']
    order = int(request.GET['order[0][column]'])
    order_dir = {'desc': '-', 'asc': ''}[request.GET['order[0][dir]']]
    length = int(request.GET['length'])
    start = int(request.GET['start'])
    draw = int(request.GET['draw'])

    records = Record.objects \
        .using(_label_db.get(project,'default')) \
        .filter(project__id=project)
    recordsTotal = len(records)

    # Filter by tag
    if selected_tag != '':
        records = records.filter(tags__contains=selected_tag)

    # Filter by search queries
    if search_value != '':
        search_queries = search_value.split(' ')
        for sq in search_queries:
            records = records.filter(
                Q(label__contains=sq) |
                Q(reason__contains=sq) |
                Q(outcome__contains=sq) |
                Q(duration__contains=sq) |
                Q(main_file__contains=sq) |
                Q(version__contains=sq) |
                Q(tags__contains=sq)
                )
    records = records.order_by(order_dir+columns[order])                        # Ordering

    data = []
    for rec in records[start:start+length]:
        data.append([
            '<a href="/%s/%s/">%s</a>' % (project, rec.label, rec.label),
            '<span style="display:none">%s</span>%s' % (rec.timestamp.strftime('%Y%m%d%H%M%S'),rec.timestamp.strftime('%d/%m/%Y %H:%M:%S')),
            '<span title="%s">%s...</span>' % (rec.reason,rec.reason[:20]),
            '<span title="%s">%s...</span>' % (rec.outcome,rec.outcome[:20]),
            ' '.join(map(lambda x: '<a href="/%s/data/datafile?path=%s&digest=%s&creation=%s">%s</a>' \
                %(project,x.path,x.digest,x.creation,x.path), rec.input_data.all())),
            ' '.join(map(lambda x: '<a href="/%s/data/datafile?path=%s&digest=%s&creation=%s">%s</a>' \
                %(project,x.path,x.digest,x.creation,x.path), rec.output_data.all())),
            '<span style="display:none">%f</span>%.2fs' % (rec.duration,rec.duration),
            '%s' % rec.launch_mode.get_parameters().get('n',1),
            '%s' % rec.executable.name,
            '%s' % rec.main_file,
            '<span title="%s">%s...</span>' % (rec.version,rec.version[:5]),# ['','*'][rec.diff]),
            '%s' % rec.script_arguments,
            # ' '.join(map(lambda tag: '<button class="btn btn-default btn-xs">%s</button>' %tag, rec.tags.split(',')))
        ])

        # Create buttons for tags
        tags = []
        if rec.tags != '':
            for tag in rec.tags.split(','):
                tags.append('<button class="btn btn-default btn-xs tag">%s</button>' %tag)
        data[-1].append(' '.join(tags))

    response_json = json.dumps({
        "draw": draw,
        "recordsTotal": recordsTotal,
        "recordsFiltered": len(records),
        "data": data
        })

    return HttpResponse(response_json,content_type="application/json")



def datatable_datakey(request, project):
    columns = ['directory', 'filename', 'digest', 'size', 'date', 'output_from_record','input_to_records']
    search_value = request.GET['search[value]']
    order = int(request.GET['order[0][column]'])
    order_dir = {'desc': '-', 'asc': ''}[request.GET['order[0][dir]']]
    length = int(request.GET['length'])
    start = int(request.GET['start'])
    draw = int(request.GET['draw'])

    datakeys = DataKey.objects.using(_label_db.get(project,'default')) \
        .filter(output_from_record__project_id=project)
    datakeysTotal = len(datakeys)

    # Filter by search queries
    if search_value != '':
        search_queries = search_value.split(' ')
        for sq in search_queries:
            datakeys = datakeys.filter(
                Q(path__contains=sq) |
                Q(digest__contains=sq) |
                Q(metadata__contains=sq) |
                Q(duration__contains=sq) |
                Q(output_from_record__label__contains=sq)
                )
    datakeys = datakeys.order_by(order_dir+columns[order])                        # Ordering

    data = []
    for dk in datakeys[start:start+length]:
        data.append([
            '%s' % dk.path,
            '<a href="/%s/%s/">%s</a>' % (project, dk.path, dk.path),
            '<span style="title:%s">%s...</span>' % (dk.digest, dk.digest[:8]),
            '%s' % (dk.get_metadata()['size']),
            '<span style="display:none">%s</span>%s' % (dk.creation.strftime('%Y%m%d%H%M%S'),dk.creation.strftime('%d/%m/%Y %H:%M:%S')),
            '<a href="/%s/%s">%s</a>' % (project,dk.output_from_record.label,dk.output_from_record.label),
            ' '.join(map(lambda x: '<a href="/%s/%s">%s</a>' % (project,x.label,x.label), dk.input_to_records.all()))
            ])

    response_json = json.dumps({
        "draw": draw,
        "recordsTotal": datakeysTotal,
        "recordsFiltered": len(datakeys),
        "data": data
        })

    return HttpResponse(response_json,content_type="application/json")


def parameter_list(request, project):
    project_obj = Project.objects.using(_label_db.get(project,'default')).get(id=project)
    main_file = request.GET.get('main_file', None)
    if main_file:
        record_list = Record.objects.using(_label_db.get(project,'default')).filter(project_id=project, main_file=main_file)
        table_id = 0
        if len(record_list) > 0:
            table_id = record_list[0].pk
        keys = []
        for record in record_list:
            try:
                parameter_set = record.parameters.to_sumatra()
                if hasattr(parameter_set, "as_dict"):
                    parameter_set = parameter_set.as_dict()
                parameter_set = parameters.nesteddictflatten(parameter_set)
                for key in parameter_set.keys():            # only works with simple parameter set
                    if key not in keys:
                        keys.append(key)
                keys.sort()
            except:
                return Http404
        return render_to_response('parameter_list.html',{'project':project_obj, 'object_list':record_list, 'keys': keys, 'main_file':main_file, 'id':table_id})
    else:
        return render_to_response('parameter_list.html',{'project':project_obj})


def image_thumbgrid(request, project):
    project_obj = Project.objects.using(_label_db.get(project,'default')).get(id=project)
    if request.is_ajax():
        offset = int(request.GET.get('offset',0))
        limit = int(request.GET.get('limit',8))
        selected_tag = request.GET.get('selected_tag', 'None')
        if selected_tag != 'None':
            record_all = Record.objects.using(_label_db.get(project,'default')).filter(project_id=project, tags__contains=selected_tag)
        else:
            record_all = Record.objects.using(_label_db.get(project,'default')).filter(project_id=project)

        data = []
        for record in record_all:
            tags = [tag.name for tag in record.tag_objects()]
            for data_key in record.output_data.filter(metadata__contains='image'):
                data.append({
                    'project_name':     project_obj.id,
                    'label':            record.label,
                    'main_file':        record.main_file,
                    'repos_url':        record.repository.url,
                    'version':          record.version,
                    'reason':           record.reason,
                    'outcome':          record.outcome,
                    'tags':             tags,
                    'path':             data_key.path,
                    'creation':         data_key.creation.strftime('%Y-%m-%d %H:%M:%S'),
                    'digest':           data_key.digest
                })
        if limit != -1:
            return HttpResponse(json.dumps(data[offset:offset+limit]), content_type='application/json')
        else:
            return HttpResponse(json.dumps(data), content_type='application/json')
    else:
        tags = Tag.objects.using(_label_db.get(project,'default')).all()
        return render_to_response('image_thumbgrid.html', {'project':project_obj, 'tags':tags})


def delete_records(request, project):
    if django_settings.READ_ONLY:
        return HttpResponse('It is in read-only mode.')
    records_to_delete = request.POST.getlist('delete[]')
    delete_data = request.POST.get('delete_data', False)
    if isinstance(delete_data, str):
        # Convert strings returned from Javascript function into Python bools
        delete_data = {'false': False, 'true': True}[delete_data]
    records = Record.objects.using(_label_db.get(project,'default')).filter(label__in=records_to_delete, project__id=project)
    if records:
        for record in records:
            if delete_data:
                datastore = record.datastore.to_sumatra()
                datastore.delete(*[data_key.to_sumatra()
                                   for data_key in record.output_data.all()])
            record.delete()
    return HttpResponse('OK')


def show_content(request, datastore_id):
    datastore = Datastore.objects.using(_label_db.get(project,'default')).get(pk=datastore_id).to_sumatra()
    attrs = dict(path=request.GET['path'],
                 digest=request.GET['digest'],
                 creation=datestring_to_datetime(request.GET['creation']))
    data_key = DataKey.objects.using(_label_db.get(project,'default')).get(**attrs).to_sumatra()
    mimetype = data_key.metadata["mimetype"]
    try:
        content = datastore.get_content(data_key)
    except (IOError, KeyError):
        raise Http404
    return HttpResponse(content, content_type=mimetype or "application/unknown")


def show_script(request, project):
    """ get the script content from the repos """
    if os.path.exists(os.path.join(os.getcwd(),project)):
        path = os.path.join(os.getcwd(),project)
    else:
        path = os.getcwd()
    wc = get_working_copy(path)
    digest = request.GET.get('digest', False)
    main_file = request.GET.get('main_file', False)
    try:
        file_content = wc.content(digest, main_file)
    except:
        raise Http404
    return HttpResponse('<p><span style="font-size: 15px; font-weight:bold">'+main_file+'</span> <span class="label">'+digest+'</span></p><hr>'+file_content.replace(' ','&#160;').replace('\n', '<br />'))


def compare_records(request, project):
    record_labels = [request.GET['a'], request.GET['b']]
    db_records = Record.objects.using(_label_db.get(project,'default')).filter(label__in=record_labels, project__id=project)
    records = [r.to_sumatra() for r in db_records]
    diff = RecordDifference(*records)
    context = {'db_records': db_records,
               'diff': diff,
               'project': Project.objects.using(_label_db.get(project,'default')).get(pk=project)}
    if diff.input_data_differ:
        context['input_data_pairs'] = pair_datafiles(diff.recordA.input_data, diff.recordB.input_data)
    if diff.output_data_differ:
        context['output_data_pairs'] = pair_datafiles(diff.recordA.output_data, diff.recordB.output_data)
    return render_to_response("record_comparison.html", context)



def pair_datafiles(data_keys_a, data_keys_b, threshold=0.7):
    import difflib
    from os.path import basename
    from copy import copy

    unmatched_files_a = copy(data_keys_a)
    unmatched_files_b = copy(data_keys_b)
    matches = []
    while unmatched_files_a and unmatched_files_b:
        similarity = []
        n2 = len(unmatched_files_b)
        for x in unmatched_files_a:
            for y in unmatched_files_b:
                # should check mimetypes. Different mime-type --> similarity set to 0
                similarity.append(
                    difflib.SequenceMatcher(a=basename(x.path),
                                            b=basename(y.path)).ratio())
        s_max = max(similarity)
        if s_max > threshold:
            i_max = similarity.index(s_max)
            matches.append((
                unmatched_files_a.pop(i_max%n2),
                unmatched_files_b.pop(i_max//n2)))
        else:
            break
    return {"matches": matches,
            "unmatched_a": unmatched_files_a,
            "unmatched_b": unmatched_files_b}


def plot_file(request, project):
    query = request.GET.copy()
    query['path_list'] = request.GET.getlist('path')
    return render_to_response(request.GET['template'], query)


class SettingsView(View):

    def get(self, request):
        return HttpResponse(json.dumps(self.load_settings()), content_type='application/json')

    def post(self, request):
        if django_settings.READ_ONLY:
            return HttpResponse('It is in read-only mode.')
        table_settings = self.load_settings()
        data = json.loads(request.body.decode('utf-8'))
        table_settings.update(data["settings"])
        self.save_settings(table_settings)
        return HttpResponse('OK')

    def load_settings(self):
        if os.path.exists(global_conf_file):
            with open(global_conf_file, 'r') as fp:
                table_settings = json.load(fp)
        else:
            table_settings = {
                "hidden_cols": []
            }
        return table_settings

    def save_settings(self, settings):
        with open(global_conf_file, 'w') as fp:
            json.dump(settings, fp)
