"""
HTML forms
(part of web.py)
"""

import copy, re
import webapi as web
import utils, net

def attrget(obj, attr, value=None):
    if hasattr(obj, 'has_key') and obj.has_key(attr): return obj[attr]
    return getattr(obj, attr) if hasattr(obj, attr) else value

class Form:
    r"""
    HTML form.
    
        >>> f = Form(Textbox("x"))
        >>> f.render()
        '<table>\n    <tr><th><label for="x">x</label></th><td><input type="text" name="x" id="x" /></td></tr>\n</table>'
    """
    def __init__(self, *inputs, **kw):
        self.inputs = inputs
        self.valid = True
        self.note = None
        self.validators = kw.pop('validators', [])

    def __call__(self, x=None):
        o = copy.deepcopy(self)
        if x: o.validates(x)
        return o
    
    def render(self):
        out = ''
        out += self.rendernote(self.note)
        out += '<table>\n'
        for i in self.inputs:
            out += f'    <tr><th><label for="{i.id}">{net.websafe(i.description)}</label></th>'
            out += f"<td>{i.pre}{i.render()}{i.post}" + "</td></tr>\n"
        out += "</table>"
        return out
        
    def render_css(self): 
        out = [self.rendernote(self.note)]
        for i in self.inputs: 
            out.extend(
                (
                    f'<label for="{i.id}">{net.websafe(i.description)}</label>',
                    i.pre,
                )
            )
            out.extend((i.render(), i.post, '\n'))
        return ''.join(out) 
        
    def rendernote(self, note):
        return f'<strong class="wrong">{net.websafe(note)}</strong>' if note else ""
    
    def validates(self, source=None, _validate=True, **kw):
        source = source or kw or web.input()
        out = True
        for i in self.inputs:
            v = attrget(source, i.name)
            if _validate:
                out = i.validate(v) and out
            else:
                i.value = v
        if _validate:
            out = out and self._validate(source)
            self.valid = out
        return out

    def _validate(self, value):
        self.value = value
        for v in self.validators:
            if not v.valid(value):
                self.note = v.msg
                return False
        return True

    def fill(self, source=None, **kw):
        return self.validates(source, _validate=False, **kw)
    
    def __getitem__(self, i):
        for x in self.inputs:
            if x.name == i: return x
        raise KeyError, i

    def __getattr__(self, name):
        # don't interfere with deepcopy
        inputs = self.__dict__.get('inputs') or []
        for x in inputs:
            if x.name == name: return x
        raise AttributeError, name
    
    def get(self, i, default=None):
        try:
            return self[i]
        except KeyError:
            return default
            
    def _get_d(self): #@@ should really be form.attr, no?
        return utils.storage([(i.name, i.value) for i in self.inputs])
    d = property(_get_d)

class Input(object):
    def __init__(self, name, *validators, **attrs):
        self.description = attrs.pop('description', name)
        self.value = attrs.pop('value', None)
        self.pre = attrs.pop('pre', "")
        self.post = attrs.pop('post', "")
        self.id = attrs.setdefault('id', name)
        if 'class_' in attrs:
            attrs['class'] = attrs['class_']
            del attrs['class_']
        self.name, self.validators, self.attrs, self.note = name, validators, attrs, None

    def validate(self, value):
        self.value = value
        for v in self.validators:
            if not v.valid(value):
                self.note = v.msg
                return False
        return True

    def render(self): raise NotImplementedError

    def rendernote(self, note):
        return f'<strong class="wrong">{net.websafe(note)}</strong>' if note else ""
        
    def addatts(self):
        return "".join(f' {n}="{net.websafe(v)}"' for n, v in self.attrs.items())
    
#@@ quoting

class Textbox(Input):
    def render(self, shownote=True):
        x = f'<input type="text" name="{net.websafe(self.name)}"'
        if self.value:
            x += f' value="{net.websafe(self.value)}"'
        x += self.addatts()
        x += ' />'
        if shownote:
            x += self.rendernote(self.note)
        return x

class Password(Input):
    def render(self):
        x = f'<input type="password" name="{net.websafe(self.name)}"'
        if self.value:
            x += f' value="{net.websafe(self.value)}"'
        x += self.addatts()
        x += ' />'
        x += self.rendernote(self.note)
        return x

class Textarea(Input):
    def render(self):
        x = f'<textarea name="{net.websafe(self.name)}"'
        x += self.addatts()
        x += '>'
        if self.value is not None: x += net.websafe(self.value)
        x += '</textarea>'
        x += self.rendernote(self.note)
        return x

class Dropdown(Input):
    def __init__(self, name, args, *validators, **attrs):
        self.args = args
        super(Dropdown, self).__init__(name, *validators, **attrs)

    def render(self):
        x = '<select name="%s"%s>\n' % (net.websafe(self.name), self.addatts())
        for arg in self.args:
            value, desc = arg if type(arg) == tuple else (arg, arg)
            select_p = ' selected="selected"' if self.value == value else ''
            x += '  <option %s value="%s">%s</option>\n' % (select_p, net.websafe(value), net.websafe(desc))
        x += '</select>\n'
        x += self.rendernote(self.note)
        return x

class Radio(Input):
    def __init__(self, name, args, *validators, **attrs):
        self.args = args
        super(Radio, self).__init__(name, *validators, **attrs)

    def render(self):
        x = '<span>'
        for arg in self.args:
            select_p = ' checked="checked"' if self.value == arg else ''
            x += f'<input type="radio" name="{net.websafe(self.name)}" value="{net.websafe(arg)}"{select_p}{self.addatts()} /> {net.websafe(arg)} '
            x += '</span>'
            x += self.rendernote(self.note)
        return x

class Checkbox(Input):
    def render(self):
        x = f'<input name="{net.websafe(self.name)}" type="checkbox"'
        if self.value: x += ' checked="checked"'
        x += self.addatts()
        x += ' />'
        x += self.rendernote(self.note)
        return x

class Button(Input):
    def __init__(self, name, *validators, **attrs):
        super(Button, self).__init__(name, *validators, **attrs)
        self.description = ""

    def render(self):
        safename = net.websafe(self.name)
        x = f'<button name="{safename}"{self.addatts()}>{safename}</button>'
        x += self.rendernote(self.note)
        return x

class Hidden(Input):
    def __init__(self, name, *validators, **attrs):
        super(Hidden, self).__init__(name, *validators, **attrs)
        # it doesnt make sence for a hidden field to have description
        self.description = ""

    def render(self):
        x = f'<input type="hidden" name="{net.websafe(self.name)}"'
        if self.value:
            x += f' value="{net.websafe(self.value)}"'
        x += self.addatts()
        x += ' />'
        return x

class File(Input):
    def render(self):
        x = f'<input type="file" name="{net.websafe(self.name)}"'
        x += self.addatts()
        x += ' />'
        x += self.rendernote(self.note)
        return x
    
class Validator:
    def __deepcopy__(self, memo): return copy.copy(self)
    def __init__(self, msg, test, jstest=None): utils.autoassign(self, locals())
    def valid(self, value): 
        try: return self.test(value)
        except: return False

notnull = Validator("Required", bool)

class regexp(Validator):
    def __init__(self, rexp, msg):
        self.rexp = re.compile(rexp)
        self.msg = msg
    
    def valid(self, value):
        return bool(self.rexp.match(value))

if __name__ == "__main__":
    import doctest
    doctest.testmod()
