"""Support for JavaScript interface."""

# Copyright © 2026, Ethan I. Schaefer (eschaefer@seti.org)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.

###############################################################################
# region> IMPORT
###############################################################################
# Special.
from __future__ import annotations

# Standard.
import collections as _collections
import copy as _copy
import functools as _functools
import inspect as _inspect
import itertools as _itertools
import re as _re
import textwrap as _textwrap
import types as _types
import typing as _typing


# endregion
###############################################################################
# region> NUMPY DOC PARSING
###############################################################################
class Complement:
    """Reports as not containing only those elements in its `.set`."""

    def __init__(
        self,
        elements: _collections.abc.Iterable[_collections.abc.Hashable] = (),
    ) -> None:
        self.set = set(elements)

    def __contains__(self, item):
        return item not in self.set


# endregion
###############################################################################
# region> NUMPY DOC PARSING
###############################################################################
# Note: Avoids adding `numpydoc` as a dependency.
type ContentItem = tuple[str, list[str] | None]
type Content = str | dict[str, ContentItem] | None


class NumpyDoc:
    def __init__(
        self, func: _collections.abc.Callable, *, copy: bool = False
    ) -> None:
        """
        Create an instance to help merge docstrings and wrap functions.

        Parameters
        ----------
        func : collections.abc.Callable
            The terminal function or other callable. Note that there is
            limited support for callables (such as classes) that are not
            `types.FunctionType`.
        copy : bool, default=False
            Whether to deep-copy `func` before assigning it to `.func`.
            If `False`, `func` is modified in place.
        """
        if copy:
            func = copy_function(func)  # *REASSIGNMENT*
        self.func = func

    # * CONTENT UTILITIES. ────────────────────────────────────────────
    def _combine_contents(
        self,
        content_a: Content,
        content_b: Content,
        *,
        a_is_nominal: bool | None = None,
    ) -> Content:
        # Return one content if the other is `None`.
        if content_a is None:
            return content_b
        if content_b is None:
            return content_a

        # Validate content types.
        if not isinstance(content_a, type(content_b)):
            raise TypeError("Contents must each be of same type (or `None`).")

        # Concatenate string contents.
        if isinstance(content_a, str):
            return "\n\n".join((content_a, content_b))

        # Resolve `title2` (string) component.
        if a_is_nominal is None:
            raise TypeError(
                "Must specify `a_is_nominal` when contents are not strings."
            )
        title2_a, resid_a = content_a
        title2_b, resid_b = content_b
        if a_is_nominal:
            title2 = title2_a
        else:
            title2 = title2_b

        # Resolve `resid` (line list) component.
        if resid_a is None:
            resid = resid_b
        elif resid_b is None:
            resid = resid_a
        elif resid_a[-1].startswith(" "):
            resid = resid_a + resid_b
        else:
            resid_a_copy = resid_a.copy()
            resid_b_copy = resid_b.copy()
            resid_ab_temp = [resid_a_copy.pop()]
            for line in resid_b:
                if line.startswith(" "):
                    break
                resid_ab_temp.append(resid_b_copy.pop(0))
            resid_ab_final = _textwrap.fill(
                "\n".join(resid_ab_temp), 68
            ).splitlines()
            resid = [*resid_a_copy, *resid_ab_final, *resid_b_copy]

        # Return.
        return (title2, resid)

    def _get_value(
        self,
        key: str | int,
        *,
        parent: str | int | None,
    ) -> _typing.Any:
        if parent is None:
            return self.section_name_to_content[key]
        content_mapping = self.section_name_to_content[parent]
        if content_mapping is None:
            return None
        else:
            return content_mapping.get(key)

    def _resolve_content(
        self,
        key: str | int,
        *,
        parent: str | None = None,
        inherited: NumpyDoc,
        exclude_set: set[str | int] | Complement,
        extend_set: set[str | int],
        prepend_set: set[str | int],
    ) -> Content | ContentItem:
        # Collect nominal and inherited content.
        nom_content = self._get_value(key, parent=parent)
        if key in exclude_set:
            return nom_content
        inherited_content = inherited._get_value(key, parent=parent)

        # Determine merge behavior, honoring parent's default.
        merge_type = None  # Initialize.
        merge_type_to_set = {
            "exclude": exclude_set,
            "extend": extend_set,
            "prepend": prepend_set,
        }
        for k in (key, parent):
            if k is None:
                continue
            for cand_merge_type, set_ in merge_type_to_set.items():
                if k in set_:
                    merge_type = cand_merge_type
                    break
            else:
                continue
            break  # Cascade.
        if merge_type is None:
            merge_type = "prepend"  # Default.

        # Merge (or abort).
        if merge_type == "exclude":
            return nom_content
        if nom_content is None:
            return inherited_content
        if inherited_content is None:
            return nom_content
        match merge_type:
            case "prepend":
                return self._combine_contents(
                    inherited_content, nom_content, a_is_nominal=False
                )
            case "extend":
                return self._combine_contents(
                    nom_content, inherited_content, a_is_nominal=True
                )
            case _:
                raise TypeError(
                    f"`merge_type` is not recognized {merge_type!r}"
                )

    def _resolve_section_content(
        self,
        section_key: str | int,
        *,
        inherited: NumpyDoc,
        exclude_set: set[str | int] | Complement,
        extend_set: set[str | int],
        prepend_set: set[str | int],
    ) -> Content:
        # Resolve section content from each source.
        nom_content = self.section_name_to_content[section_key]
        inherited_content = inherited.section_name_to_content[section_key]

        # If content is string-based or null, resolve it directly.
        if nom_content is None and inherited_content is None:
            return None
        if isinstance(nom_content, str) or isinstance(inherited_content, str):
            return self._resolve_content(
                section_key,
                inherited=inherited,
                exclude_set=exclude_set,
                extend_set=extend_set,
                prepend_set=prepend_set,
            )

        # Otherwise, combine sub-section keys and compile content.
        final_content = {}
        for content in (nom_content, inherited_content):
            if content is None:
                continue
            if section_key == "Parameters":
                ordered_keys = self.param_names
            else:
                ordered_keys = content
            for key in ordered_keys:
                if key in final_content:
                    continue
                new_content = self._resolve_content(
                    key,
                    parent=section_key,
                    inherited=inherited,
                    exclude_set=exclude_set,
                    extend_set=extend_set,
                    prepend_set=prepend_set,
                )
                if new_content is None:
                    continue
                final_content[key] = new_content
        return final_content

    # * FUNCTION-WRAPPING UTILITIES. ──────────────────────────────────
    def _get_signature(
        self, func: _collections.abc.Callable | None = None
    ) -> _inspect.Signature:
        if func is None:
            func = self.func  # *REASSIGNMENT*
        # Note: `eval_str=True` ensures that every type used in
        # annotations is resolved. Otherwise, for example, merging
        # signatures could result in unresolvable forward references.
        sig = _inspect.signature(func, eval_str=True)
        return sig

    def _merge_signatures(
        self,
        other: _collections.abc.Callable,
        *,
        exclude_set: set[str | int] | Complement,
        drop_args: bool,
        drop_kwargs: bool,
        as_keywords: bool,
    ) -> None:
        # Merge signatures.
        kind_to_params = _collections.defaultdict(list)
        nom_sig = self._get_signature()
        other_sig = self._get_signature(other)
        seen = set()
        for func, sig, force_kw, excluded in (
            (self.func, nom_sig, False, ()),
            (other, other_sig, as_keywords, exclude_set),
        ):
            for param in sig.parameters.values():
                if param.name in excluded or param.name in seen:
                    continue
                seen.add(param.name)
                if force_kw:
                    # *REASSIGNMENT*
                    param = param.replace(kind=_inspect.Parameter.KEYWORD_ONLY)
                kind_to_params[param.kind].append(param)
            if func is self.func:
                if drop_args:
                    kind_to_params[_inspect.Parameter.VAR_POSITIONAL].clear()
                if drop_kwargs:
                    kind_to_params[_inspect.Parameter.VAR_KEYWORD].clear()
        name_to_param = {
            param.name: param
            for kind in _inspect._ParameterKind
            for param in kind_to_params[kind]
        }
        merged_sig = nom_sig.replace(parameters=name_to_param.values())
        self._set_signature(merged_sig)

    def _set_signature(self, signature: _inspect.Signature) -> None:
        self.func.__signature__ = signature
        self._update_signature_related()

    def _update_signature_related(self) -> None:
        annotations = {}
        defaults = []
        kwdefaults = {}
        for param in self._get_signature().parameters.values():
            if param.annotation is not param.empty:
                annotations[param.name] = param.annotation
            if param.default is param.empty:
                continue
            match param.kind:
                case (
                    _inspect.Parameter.POSITIONAL_OR_KEYWORD
                    | _inspect.Parameter.POSITIONAL_ONLY
                ):
                    defaults.append(param.default)
                case _inspect.Parameter.KEYWORD_ONLY:
                    kwdefaults[param.name] = param.default
                case _:
                    continue
        if "return" in self.func.__annotations__:
            annotations["return"] = self.func.__annotations__["return"]
        self.func.__annotations__ = annotations
        self.func.__defaults__ = tuple(defaults)
        self.func.__kwdefaults__ = kwdefaults

    # * DATA ATTRIBUTES. ──────────────────────────────────────────────
    _section_names = (
        0,  # Short Summary
        1,  # Extended Summary
        "Parameters",
        "Attributes",
        "Returns",
        "Raises",
        "Warnings",
        "See Also",
        "Notes",
        "Examples",
    )
    _structured_section_names = (
        "Parameters",
        "Attributes",
        "Returns",
        "Raises",
        "See Also",
    )
    assert set(_structured_section_names).issubset(_section_names)

    @property
    def docstring(self) -> str | None:
        """The current docstring, reflecting any wrapping."""
        if "section_name_to_content" not in self.__dict__:
            if self.func.__doc__ is None:
                return None
            else:
                return _inspect.cleandoc(self.func.__doc__)
        blocks = []
        for section_name, content in self.section_name_to_content.items():
            if not content:  # `None` or `{}`
                continue
            if isinstance(section_name, str):
                blocks.append(section_name)
                blocks.append("-" * len(section_name))
            if isinstance(content, dict):
                for title1, (title2, lines) in content.items():
                    line1 = "".join((title1, title2))
                    if lines is None:
                        block = line1
                    else:
                        line_subblock = _textwrap.indent(
                            "\n".join(lines), self.indent + "    "
                        )
                        block = "\n".join((line1, line_subblock))
                    blocks.append(block)
            else:
                blocks.append(content)
            blocks.append("")
        del blocks[-1]
        return "\n".join(blocks)

    @_functools.cached_property
    def indent(self) -> str:
        """The indentation string for the terminal docstring."""
        match = _re.search("^ *", self.section_name_to_content[0])
        if match is None:
            return ""
        else:
            return match.group()

    @property
    def param_names(self) -> tuple[str, ...]:
        """Parameter names, including prefixed *'s where appropriate."""
        full_param_names = []
        for param in self._get_signature().parameters.values():
            match param.kind:
                case _inspect.Parameter.VAR_POSITIONAL:
                    prefix = "*"
                case _inspect.Parameter.VAR_KEYWORD:
                    prefix = "**"
                case _:
                    prefix = ""
            full_param_name = f"{prefix}{param.name}"
            full_param_names.append(full_param_name)
        return tuple(full_param_names)

    @_functools.cached_property
    def section_name_to_content(self) -> dict[str | int, Content]:
        """Mapping of section names to content."""
        # Make empty mapping to fill.
        section_name_to_content = dict.fromkeys(self._section_names)

        # Crudely parse docstring and split off summaries.
        parsed = _re.split(r"(?i)([a-z0-9 ]+)\n-{4,}\n", self.docstring)
        summ_lines = parsed.pop(0).splitlines(keepends=True)
        section_name_to_content[0] = summ_lines[0].rstrip()
        # Note: `2` ignores empty line following short summary.
        if len(summ_lines) > 2:
            section_name_to_content[1] = "".join(summ_lines[2:]).rstrip()
        else:
            section_name_to_content[1] = None

        # Slot in each found section.
        for section_name, content in _itertools.batched(
            parsed, 2, strict=True
        ):
            if section_name not in section_name_to_content:
                raise TypeError(
                    f"Section name not recognized: {section_name!r}"
                )
            clean_content = content.rstrip()

            # Identify placeholder content.
            if clean_content and (
                clean_content == "..."
                or (clean_content[0] == "<" and clean_content[-1] == ">")
            ):
                clean_content = None

            # Parse structured section.
            elif section_name in self._structured_section_names:
                clean_text = clean_content
                clean_content = {}  # *REASSIGNMENT*
                for match in _re.finditer(
                    r"(?m)(?P<title1>^\S+)(?P<title2>.*)(?P<resid>(\n .*)+)?",
                    clean_text,
                ):
                    # for match in _re.finditer(
                    #     r"(?ms)(?P<title1>^\S+)(?P<title2>.*?(?:\n|\Z))"
                    #     r"(?P<resid>.+?(?=\n\S|\Z))?",
                    #     clean_text,
                    # ):
                    title1 = match.group("title1")
                    title2 = match.group("title2")
                    resid = match.group("resid")
                    if (
                        not resid
                        or resid == "***"
                        or (resid[0] == "<" and resid[-1] == ">")
                    ):
                        resid = None  # *REASSIGNMENT*
                    elif resid is not None:
                        # Note: Remove leading carriage return.
                        # *REASSIGNMENT*
                        resid = _textwrap.dedent(resid[1:]).splitlines()
                    clean_content[title1] = (title2, resid)

            # Store final content.
            section_name_to_content[section_name] = clean_content

        # Return mapping.
        return section_name_to_content

    # * PUBLIC METHODS. ───────────────────────────────────────────────
    def annotate_params(
        self,
        *,
        make_metadata: (
            _collections.abc.Callable[[_inspect.Parameter, str], _typing.Any]
            | None
        ) = None,
        delete_section: bool = False,
    ) -> None:
        """
        Annotate each parameter with its docstring or other metadata.

        Each parameter in `.func`'s signature is replaced with an instance like
            ``typing.Annotated[type_hint, metadata]``

        Parameters
        ----------
        make_metadata : collections.abc.Callable, optional
            Any callable that accepts two positional arguments: the relevant
            ``inspect.Parameter`` instance and the parameter's docstring. Its
            returned value is used as `metadata`. If not specified (or `None`),
            the docstring itself is used.
        delete_section : bool, default=False
            Whether to delete the Parameters section in `.func`'s docstring.

        Returns
        -------
        None
        """
        # Iterate over each parameter in the signature.
        cur_sig = self._get_signature()
        new_params = []
        pname_to_content_item = self.section_name_to_content["Parameters"]
        for param in cur_sig.parameters.values():
            # Provisionally use existing `Parameter`.
            new_params.append(param)

            # If signature has no annotation or no documentation, there
            # is nothing to do.
            cur_ptype = param.annotation
            if cur_ptype is param.empty:
                continue
            content_item = pname_to_content_item.get(param.name)
            if content_item is None:
                continue

            # Annotate parameter with documentation metadata.
            title2, lines = content_item
            # Note: `title2` is intentionally dropped.
            metadata = "\n".join(lines)
            if make_metadata is not None:
                metadata = make_metadata(param, metadata)  # *REASSIGNMENT*
            new_ptype = _typing.Annotated[cur_ptype, metadata]
            new_params[-1] = param.replace(annotation=new_ptype)

        # Optionally delete Parameters section.
        if delete_section:
            self.replace_section("Parameters", None)

        # Store updated signature.
        new_sig = cur_sig.replace(parameters=new_params)
        self._set_signature(new_sig)

    def check_param_doc_completeness(self) -> None:
        """
        Check whether each parameter in the call signature is documented.

        If any parameter is not documented, an exception is raised.

        Returns
        -------
        None

        Raises
        ------
        TypeError
            If any parameter is not documented.
        """
        param_name_to_content = self.section_name_to_content["Parameters"]
        if param_name_to_content is None:
            raise TypeError("Parameters section is missing!")
        for key in self.param_names:
            content = param_name_to_content.get(key)
            if content is None:
                raise TypeError(f"Missing content for parameter: {key}")

    def copy_param_docs_from(self, source: _collections.abc.Callable) -> None:
        """
        Prepend parameter docstrings from a souce.

        Each parameter of `.func` that is documented by `source` will have its
        docstring prepended to the corresponding parameter docstring of
        `.func`. If `.func` has the parameter but no docstring, then the
        docstring from `source` is set directly.

        Parameters
        ----------
        source : collections.abc.Callable
            The source from which parameter docstrings will be copied.

        Returns
        -------
        None

        See Also
        --------
        wrap : Fully merge signatures and docstrings for two callables
        """
        nom_params_content = self.section_name_to_content["Parameters"]
        if nom_params_content is None:
            new_params_content = {}
        else:
            new_params_content = nom_params_content.copy()
        inherited_params_content = NumpyDoc(source).section_name_to_content[
            "Parameters"
        ]
        for param_name in self._get_signature().parameters:
            nom_content = new_params_content.get(param_name)
            inherited_content = inherited_params_content.get(param_name)
            new_content = self._combine_contents(
                inherited_content, nom_content, a_is_nominal=False
            )
            new_params_content[param_name] = new_content
        self.section_name_to_content["Parameters"] = new_params_content
        self.func.__doc__ = self.docstring

    def replace_section(self, name: str, content: Content) -> None:
        """
        Replace a section in the docstring.

        Parameters
        ----------
        name : str
            The name of the section to replace.
        content : Content
            The content with which the section will be replaced. This is most
            easily specified as a string.

        Returns
        -------
        None
        """
        if name not in self.section_name_to_content:
            raise TypeError(f"Section name not recognized: {name!r}")
        content_is_string = isinstance(content, str)
        if content_is_string:
            content = _textwrap.dedent(content.strip())  # *REASSIGNMENT*
        self.section_name_to_content[name] = content
        self.func.__doc__ = self.docstring
        # Note: If a structured section is passed as a string,
        # `.docstring` is still generated correctly but
        # `.section_name_to_content` must be primed to rebuild.
        if name in self._structured_section_names and content_is_string:
            del self.section_name_to_content

    def wrap(
        self,
        wrapped: _collections.abc.Callable,
        *,
        exclude: _collections.abc.Collection[str | int] = (),
        extend: _collections.abc.Collection[str | int] = (),
        prepend: _collections.abc.Collection[str | int] = (),
        strict: bool = False,
        drop_args: bool = True,
        drop_kwargs: bool = True,
        as_keywords: bool = False,
    ) -> None:
        """
        Register a function that is wrapped by the terminal function.

        If the terminal function (`.func`) is deeply wrapped, call the current
        function from the terminal end upward. For example, if `outer()` calls
        `middle()` which itself calls `inner()`, then initialize a `NumpyDoc`
        instance with `outer` as `func`, then call `wrap(middle)` and finally
        `wrap(inner)`. Or, if appropriate, you can initialize a `NumpyDoc`
        for `middle`, call `wrap(inner)`, and then initialize a `NumpyDoc`
        instance for `outer` and call `wrap(middle)` only, since the `NumpyDoc`
        machinery modifies `.func` in place (modifying the signature and
        related records, as well as the docstring).

        In the three collection parameters (`exclude`, `extend`, and
        `prepend`), you can specify Numpy docstring sections and "subsections".
        Sections include `"Examples"`, `"Notes"`, `"See Also"`, etc. Use `0` to
        specify the first line of the docstring, called the short summary, and
        `1` to specify the lines in the extended summary that follows the short
        summary. Subsections include individual parameter names (which each
        form a subsection within Parameters), exception names (which each form
        a subsection within Raises), etc.

        Within the collection parameters, sections that are specified but
        unrecognized (unsupported) will raise an exception. Specified sections
        that are merely unused and specified subsections that are unrecognized
        or unused are ignored. For section and subsections that are present but
        not specified, each is allocated to one of the collection parameters as
        follows:
            (1) If `strict` is `True`, all unspecified sections and subsections
                default to `exclude`. Otherwise, continue to (2).
            (2) An unspecified subsection inherits the specified behavior of
                its parent section, if any.
            (3) The following sections default to `exclude`: `0`, `"See Also"`,
                and `"Examples"`. If "Returns" is populated for `.func`, it is
                also excluded by default. All other sections, and all non-
                excluded subsections, default to `prepend`.

        Some unexpected argument-value combinations have undocumented behavior
        and are not recommended, such as specifying `0` anywhere other than
        `exclude` (to which it defaults). However, individual parameter names
        may be specified.

        If you wish, you may populate any section or subsection with one of two
        placeholders: `"..."` or any text bracketed by `"<"` and `">"`. In both
        cases, the contents are ignored and replaced with the content from
        `wrapped` counterparts (if those contents are not excluded). The
        latter, bracketed form enables you to include a note in the hard-coded
        docstring to explain that the section is populated with content from
        `wrapped` at runtime.

        Parameter subsections always follow the signature of `.func`, and that
        signature is extended with parameters from `wrapped` unless specified
        in `exclude`. (See the documentations for that parameter.) The
        parameter type in `.docstring` is never modified during extending or
        prepending. The return annotation of `.func` is also never modified.

        Parameters
        ----------
        wrapped : collections.abc.Callable
            The function that `.func` wraps.
        exclude : collections.abc.Collection[str | int]
            The Numpy docstring sections and subsections of `wrapped` that
            should be ignored. When a parameter name is specified, it is also
            excluded from the signature of `.func`. Otherwise, any parameters
            of `wrapped` absent from `.func` are added to `.func` as determined
            by `as_keywords`.
        extend : collections.abc.Collection[str | int]
            The Numpy docstring sections and subsections of `wrapped` that
            should come after their counterparts in `.func`. New section
            components are added as new paragraphs, and new subsection
            components are text-wrapped within the same paragraph.
        prepend : collections.abc.Collection[str | int]
            The Numpy docstring sections and subsections of `wrapped` that
            should precede their counterparts in `.func`. New section
            components are added as new paragraphs, and new subsection
            components are text-wrapped within the same paragraph.
        strict : bool, default=False
            Whether to ignore any section or subsection not explicitly named in
            `extend` or `prepend`. If `False`, assignment of such unnamed
            components is made on a best-guess basis.
        drop_args : bool, default=True
            Whether to discard any unbound positional (`*args`-like) argument
            of `.func` before merging. If `wrapped` has such an argument, it is
            attached to `.func` unless excluded. If `False` and `wrapped` has
            such an argument, an exception is raised.
        drop_kwargs : bool, default=True
            Whether to discard any unbound keyword (`**kwargs`-like) argument
            of `.func` before merging. If `wrapped` has such an argument, it is
            attached to `.func` unless excluded. If `False` and `wrapped` has
            such an argument, an exception is raised.
        as_keywords : bool, default=False
            Whether, when parameters from `wrapped` are added to `.func`, they
            should be keyword-only rather than their kind in `wrapped`.

        Raises
        ------
        TypeError
            If an unsupported section name is specified, the same value occurs
            in multiple collection parameters, or other unexpected cases.

        Returns
        -------
        None

        See Also
        --------
        copy_param_docs : Copy parameter docs without merging signatures
        """
        # Finalize configuration.
        overrides = (*exclude, *extend, *prepend)
        override_set = set(overrides)
        if len(override_set) < len(overrides):
            raise TypeError(
                "Cannot repeat values between "
                "`exclude`, `extend`, and `prepend`."
            )
        extend_set = set(extend)
        # Note: `prepend_set` is used when a child (such as a parameter)
        # should prepend even though its parent (such as "Parameters")
        # has different default behavior.
        prepend_set = set(prepend)
        if strict:
            exclude_set = Complement(extend_set | prepend_set)
        else:
            exclude_set = {0, "See Also", "Examples"}
            if self.section_name_to_content["Returns"] is not None:
                exclude_set.add("Returns")
            exclude_set -= override_set
            exclude_set.update(exclude)
        del exclude, extend, prepend

        # Merge signatures and related.
        self._merge_signatures(
            wrapped,
            exclude_set=exclude_set,
            drop_args=drop_args,
            drop_kwargs=drop_kwargs,
            as_keywords=as_keywords,
        )

        # Merge docstrings.
        inherited = NumpyDoc(wrapped)
        self.section_name_to_content = {
            section_name: self._resolve_section_content(
                section_name,
                inherited=inherited,
                exclude_set=exclude_set,
                extend_set=extend_set,
                prepend_set=prepend_set,
            )
            for section_name in self.section_name_to_content
        }
        self.func.__doc__ = self.docstring


# endregion
###############################################################################
# region> CONVENIENCE FUNCTIONS
###############################################################################
def _partially_wraps(
    target: _collections.abc.Callable, *, check: bool, **kwargs
) -> _collections.abc.Callable:
    numdoc = NumpyDoc(target)
    numdoc.wrap(**kwargs)
    if check:
        numdoc.check_param_doc_completeness()
    return numdoc.func


def _sync_param_docs_to(
    target: _collections.abc.Callable,
    *,
    sources: tuple[_collections.abc.Callable, ...],
    check: bool,
) -> _collections.abc.Callable:
    numdoc = NumpyDoc(target)
    # Note: Ensure that argument type hints are resolved. Otherwise,
    # this resolution varies between Python versions (3.14 vs. before),
    # confounding doctests (e.g., `"int`" vs. `int`).
    numdoc._set_signature(numdoc._get_signature())
    for source in reversed(sources):
        numdoc.copy_param_docs_from(source)
    if check:
        numdoc.check_param_doc_completeness()
    return target


def copy_function(func: _types.FunctionType) -> _types.FunctionType:
    """
    Deep copy a function.

    The global namespace is used directly but all other components are deep-
    copied wherever sensible. (For example, a `tuple` will simply be reused.)

    Parameters
    ----------
    func : types.FunctionType
        The function to deep copy.

    Returns
    -------
    new : types.FunctionType
        The new function.
    """
    new = _types.FunctionType(
        func.__code__,
        func.__globals__,
        func.__name__,
        _copy.deepcopy(func.__defaults__),
        func.__closure__,
        _copy.deepcopy(func.__kwdefaults__),
    )
    for attr_name in (
        _functools.WRAPPER_ASSIGNMENTS + _functools.WRAPPER_UPDATES
    ):
        setattr(new, attr_name, _copy.deepcopy(getattr(func, attr_name)))
    return new


def partially_wraps(
    wrapped: _collections.abc.Callable,
    *,
    exclude: _collections.abc.Collection[str | int] = (),
    extend: _collections.abc.Collection[str | int] = (),
    prepend: _collections.abc.Collection[str | int] = (),
    strict: bool = False,
    drop_args: bool = True,
    drop_kwargs: bool = True,
    as_keywords: bool = False,
    check: bool = True,
) -> _collections.abc.Callable:
    """
    Decorator to partially wrap a function.

    Similar to ``functools.wraps()`` but merges call signatures and
    documentation.

    Most arguments are passed to `NumpyDoc.wrap()` and are described in
    greater detail there.

    Parameters
    ----------
    wrapped : collections.abc.Callable
        The function that the decorated function partially wraps.
    exclude, extend, prepend : collections.abc.Collection[str | int]
        The Numpy docstring sections and subsections (such as parameters) of
        `wrapped` that should be ignored, extended, or prepended,
        respectively. Exclusion of parameter subsections also excludes them
        from the merged signature.
    strict : bool, default=False
        Whether to ignore any section or subsection not explicitly named in
        `extend` or `prepend`. If `False`, assignment of such unnamed
        components is made on a best-guess basis.
    drop_args, drop_kwargs : bool, default=True
        Whether to discard `*args`- and `**kwargs`-like arguments in `wrapped`.
    as_keywords : bool, default=False
        Whether, after merging signatures, all parameters from `wrapped` should
        be keyword-only rather than retain their kind from `wrapped`.
    check : bool, default=True
        Whether to raise an error if any parameter lacks documentation.

    Returns
    -------
    deocrated
        The decorated function.

    Raises
    ------
    TypeError
        If `check` is `True` and any parameter lacks documentation after
        `deocrated` and `wrapped` have been read.

    See Also
    --------
    sync_param_docs_with : Sync parameter documentation only.

    Examples
    --------
    >>> def test(a: int, b: float, *, d: str) -> int:
    ...      '''
    ...      This is a test.
    ...
    ...      This is the `test()` extended summary.
    ...
    ...      Parameters
    ...      ----------
    ...      a : int
    ...          This is a, from `test()`.
    ...      b : float
    ...          This is b, from `test()`.
    ...      d : str
    ...          This is c, from `test()`.
    ...
    ...      Returns
    ...      -------
    ...      int
    ...          Some number.
    ...      '''
    ...      return 101

    >>> def foobar(x: int) -> int:
    ...      '''
    ...      Short summary.
    ...
    ...      Parameters
    ...      ----------
    ...      x: int
    ...          This is x, from `foobar()`.
    ...
    ...      Notes
    ...      -----
    ...      This is some informative note, from `foobar()`.
    ...      '''
    ...      return 42

    >>> @partially_wraps(foobar, extend=("Notes",), strict=True)
    ... @partially_wraps(test)
    ... def test2(*args, b: list, c: str, **kwargs) -> None:
    ...     '''
    ...     This is another test.
    ...
    ...     This is the `test2` extended summary.
    ...
    ...     Parameters
    ...     ----------
    ...     b : list
    ...         This is b, from `test2()`, which accepts a `list`.
    ...     c : str
    ...         This is c, from `test2()`.
    ...
    ...     Returns
    ...     -------
    ...     None
    ...     '''
    ...     pass

    >>> help(test2)
    Help on function test2 in module lgrs.util:
    <BLANKLINE>
    test2(a: int, *, b: list, c: str, d: str) -> None
        This is another test.
    <BLANKLINE>
        This is the `test()` extended summary.
    <BLANKLINE>
        This is the `test2` extended summary.
    <BLANKLINE>
        Parameters
        ----------
        a : int
            This is a, from `test()`.
        b : list
            This is b, from `test()`. This is b, from `test2()`, which accepts a
            `list`.
        c : str
            This is c, from `test2()`.
        d : str
            This is c, from `test()`.
    <BLANKLINE>
        Returns
        -------
        None
    <BLANKLINE>
        Notes
        -----
        This is some informative note, from `foobar()`.
    <BLANKLINE>
    """  # noqa: E501
    return _functools.partial(_partially_wraps, **locals())


def sync_param_docs_with(
    *sources: _collections.abc.Callable,
    check: bool = True,
) -> _collections.abc.Callable:
    """
    Decorator to backfill parameter documentation from other functions.

    The argument order of the deocrated function is preserved.

    Parameters
    ----------
    sources : collection.Callable
        The function(s) whose parameter documentation should be used to
        populate the Parameters section of the decorated function's
        docstring. In effect, the decorated function is appended to the end
        of `sources` and all documentation for the same parameter is
        combined in that order.
    check : bool, default=True
        Whether to raise an error if any parameter lacks documentation.

    Returns
    -------
    deocrated
        The decorated function.

    Raises
    ------
    TypeError
        If `check` is `True` and any parameter lacks documentation after
        `deocrated` and all `sources` have been read.

    See Also
    --------
    wrap_partially : Merge call signatures and documentation.

    Examples
    --------
    >>> def basal_func(a: int, b: int) -> None:
    ...     '''
    ...     This is a test.
    ...
    ...     Parameters
    ...     ----------
    ...     a : int
    ...         This is a.
    ...     b : int
    ...         This is b.
    ...
    ...     Returns
    ...     -------
    ...     None
    ...     '''
    ...     pass

    >>> @sync_param_docs_with(basal_func)
    ... def derived_func(a: int, eh: float, b: int) -> None:
    ...     '''
    ...     This is another test.
    ...
    ...     Parameters
    ...     ----------
    ...     a : int
    ...         Not to be confused with `eh`.
    ...     eh : float
    ...         This is eh.
    ...
    ...     Returns
    ...     -------
    ...     None
    ...     '''
    ...     pass

    >>> help(derived_func)
    Help on function derived_func in module lgrs.util:
    <BLANKLINE>
    derived_func(a: int, eh: float, b: int) -> None
        This is another test.
    <BLANKLINE>
        Parameters
        ----------
        a : int
            This is a. Not to be confused with `eh`.
        eh : float
            This is eh.
        b : int
            This is b.
    <BLANKLINE>
        Returns
        -------
        None
    <BLANKLINE>
    """
    return _functools.partial(_sync_param_docs_to, **locals())


# endregion
