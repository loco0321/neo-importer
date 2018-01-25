from django.shortcuts import render_to_response
from django.template.context import RequestContext


def importers_index(request, importer_site):

    return render_to_response('neo_importer/importers_index.html', {'importer_site': importer_site}, RequestContext(request))