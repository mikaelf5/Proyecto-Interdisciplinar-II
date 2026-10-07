from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import CasoPerdidaForm
from .models import CasoPerdida


class CasoPerdidaListView(LoginRequiredMixin, ListView):
    model = CasoPerdida
    template_name = "perdidas/caso_list.html"
    context_object_name = "casos"
    paginate_by = 15


class CasoPerdidaCreateView(LoginRequiredMixin, CreateView):
    model = CasoPerdida
    form_class = CasoPerdidaForm
    template_name = "perdidas/caso_form.html"
    success_url = reverse_lazy("perdidas:lista")

    def form_valid(self, form):
        messages.success(self.request, "Caso de pérdida registrado correctamente.")
        return super().form_valid(form)


class CasoPerdidaUpdateView(LoginRequiredMixin, UpdateView):
    model = CasoPerdida
    form_class = CasoPerdidaForm
    template_name = "perdidas/caso_form.html"
    success_url = reverse_lazy("perdidas:lista")

    def form_valid(self, form):
        messages.success(self.request, "Caso de pérdida actualizado correctamente.")
        return super().form_valid(form)


class CasoPerdidaDeleteView(LoginRequiredMixin, DeleteView):
    model = CasoPerdida
    template_name = "perdidas/caso_confirm_delete.html"
    success_url = reverse_lazy("perdidas:lista")