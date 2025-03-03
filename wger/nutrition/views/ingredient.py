# -*- coding: utf-8 -*-

# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License

# Standard Library
import logging

# Django
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
)
from django.core.cache import cache
from django.http import (
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.shortcuts import (
    get_object_or_404,
    render,
)
from django.urls import reverse_lazy
from django.utils.translation import (
    gettext as _,
    gettext_lazy,
)
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)

# wger
from wger.nutrition.forms import (
    IngredientForm,
    UnitChooserForm,
)
from wger.nutrition.models import Ingredient
from wger.utils.cache import cache_mapper
from wger.utils.constants import PAGINATION_OBJECTS_PER_PAGE
from wger.utils.generic_views import (
    WgerDeleteMixin,
    WgerFormMixin,
)
from wger.utils.language import (
    load_ingredient_languages,
    load_language,
)


logger = logging.getLogger(__name__)


# ************************
# Ingredient functions
# ************************
class IngredientListView(ListView):
    """
    Show an overview of all ingredients
    """
    model = Ingredient
    template_name = 'ingredient/overview.html'
    context_object_name = 'ingredients_list'
    paginate_by = PAGINATION_OBJECTS_PER_PAGE

    def get_queryset(self):
        """
        Filter the ingredients the user will see by its language

        (the user can also want to see ingredients in English, in addition to his
        native language, see load_ingredient_languages)
        """
        languages = load_ingredient_languages(self.request)
        return (Ingredient.objects.accepted().filter(language__in=languages).only('id', 'name'))

    def get_context_data(self, **kwargs):
        """
        Pass additional data to the template
        """
        context = super(IngredientListView, self).get_context_data(**kwargs)
        context['show_shariff'] = True
        return context


def view(request, id, slug=None):
    template_data = {}

    ingredient = cache.get(cache_mapper.get_ingredient_key(int(id)))
    if not ingredient:
        ingredient = get_object_or_404(Ingredient, pk=id)
        cache.set(cache_mapper.get_ingredient_key(ingredient), ingredient)
    template_data['ingredient'] = ingredient
    template_data['form'] = UnitChooserForm(
        data={
            'ingredient_id': ingredient.id,
            'amount': 100,
            'unit': None
        }
    )
    template_data['show_shariff'] = True

    return render(request, 'ingredient/view.html', template_data)


class IngredientDeleteView(
    WgerDeleteMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    DeleteView,
):
    """
    Generic view to delete an existing ingredient
    """

    model = Ingredient
    fields = (
        'name',
        'energy',
        'protein',
        'carbohydrates',
        'carbohydrates_sugar',
        'fat',
        'fat_saturated',
        'fibres',
        'sodium',
    )
    template_name = 'delete.html'
    success_url = reverse_lazy('nutrition:ingredient:list')
    messages = gettext_lazy('Successfully deleted')
    permission_required = 'nutrition.delete_ingredient'

    # Send some additional data to the template
    def get_context_data(self, **kwargs):
        context = super(IngredientDeleteView, self).get_context_data(**kwargs)

        context['title'] = _('Delete {0}?').format(self.object)
        return context


class IngredientEditView(WgerFormMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Generic view to update an existing ingredient
    """

    template_name = 'form.html'
    model = Ingredient
    form_class = IngredientForm
    permission_required = 'nutrition.change_ingredient'

    def get_context_data(self, **kwargs):
        """
        Send some additional data to the template
        """
        context = super(IngredientEditView, self).get_context_data(**kwargs)
        context['title'] = _('Edit {0}').format(self.object)
        return context


class IngredientCreateView(WgerFormMixin, CreateView):
    """
    Generic view to add a new ingredient
    """
    template_name = 'form.html'
    model = Ingredient
    form_class = IngredientForm
    title = gettext_lazy('Add a new ingredient')

    def form_valid(self, form):

        form.instance.language = load_language()
        form.instance.set_author(self.request)
        return super(IngredientCreateView, self).form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        """
        Demo users can't submit ingredients
        """
        if request.user.userprofile.is_temporary:
            return HttpResponseForbidden()
        return super(IngredientCreateView, self).dispatch(request, *args, **kwargs)


class PendingIngredientListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List all ingredients pending review
    """

    model = Ingredient
    template_name = 'ingredient/pending.html'
    context_object_name = 'ingredient_list'
    permission_required = 'nutrition.change_ingredient'

    def get_queryset(self):
        """
        Only show ingredients pending review
        """
        return Ingredient.objects.filter(status=Ingredient.STATUS_PENDING) \
            .order_by('-creation_date')


@permission_required('nutrition.add_ingredient')
def accept(request, pk):
    """
    Accepts a pending user submitted ingredient
    """
    ingredient = get_object_or_404(Ingredient, pk=pk)
    ingredient.status = Ingredient.STATUS_ACCEPTED
    ingredient.save()
    ingredient.send_email(request)
    messages.success(request, _('Ingredient was successfully added to the general database'))

    return HttpResponseRedirect(ingredient.get_absolute_url())


@permission_required('nutrition.add_ingredient')
def decline(request, pk):
    """
    Declines and deletes a pending user submitted ingredient
    """
    ingredient = get_object_or_404(Ingredient, pk=pk)
    ingredient.status = Ingredient.STATUS_DECLINED
    ingredient.save()
    messages.success(request, _('Ingredient was successfully marked as rejected'))
    return HttpResponseRedirect(ingredient.get_absolute_url())
