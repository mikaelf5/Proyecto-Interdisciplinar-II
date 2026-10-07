from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView

from .models import Solicitud
from .forms import SolicitudForm


class SolicitudListView(LoginRequiredMixin, ListView):
    model = Solicitud
    template_name = "circulacion/solicitud_list.html"
    context_object_name = "solicitudes"
    paginate_by = 15


class SolicitudCreateView(LoginRequiredMixin, CreateView):
    model = Solicitud
    form_class = SolicitudForm
    template_name = "circulacion/solicitud_form.html"
    success_url = reverse_lazy("circulacion:solicitudes")

    def form_valid(self, form):
        form.instance.solicitante_id = self.request.user.id
        return super().form_valid(form)
class SolicitudDetailView(LoginRequiredMixin, DetailView):
    model = Solicitud
    template_name = "circulacion/solicitud_detail.html"
    context_object_name = "solicitud"