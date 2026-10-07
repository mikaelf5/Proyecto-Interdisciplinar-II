from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import SancionForm
from .models import Sancion


class SancionListView(LoginRequiredMixin, ListView):
    model = Sancion
    template_name = "sanciones/sancion_list.html"
    context_object_name = "sanciones"
    paginate_by = 15


class SancionCreateView(LoginRequiredMixin, CreateView):
    model = Sancion
    form_class = SancionForm
    template_name = "sanciones/sancion_form.html"
    success_url = reverse_lazy("sanciones:lista")

    def get_initial(self):
        initial = super().get_initial()
        initial["aplicada_por_id"] = self.request.user.id
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Sanción registrada correctamente.")
        return super().form_valid(form)


class SancionUpdateView(LoginRequiredMixin, UpdateView):
    model = Sancion
    form_class = SancionForm
    template_name = "sanciones/sancion_form.html"
    success_url = reverse_lazy("sanciones:lista")

    def form_valid(self, form):
        messages.success(self.request, "Sanción actualizada correctamente.")
        return super().form_valid(form)


class SancionDeleteView(LoginRequiredMixin, DeleteView):
    model = Sancion
    template_name = "sanciones/sancion_confirm_delete.html"
    success_url = reverse_lazy("sanciones:lista")