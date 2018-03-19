import nbformat as nbf
import lxml.etree as etree
import sys
import requests
import os
import string
import hashlib
import urllib2
import ast
import re


def main(argv):
    
    descriptor_template = argv[0]
    descriptor_file = argv[1]
    nb_source = argv[2]
    
    nb = nbf.read(nb_source, 4)

    tree = etree.parse(descriptor_template)
    root = tree.getroot()

    for index, cell in enumerate(nb['cells']):
    
        if str(cell['cell_type']) == 'code': 
        
            try:
                root_ast = ast.parse(str(cell['source']))
                names = list({node.id for node in ast.walk(root_ast) if isinstance(node, ast.Name)})
           
                if len(names) == 1:
            
                    if names[0] == 'input_reference': #and action == 'runtime':
                    
                        el_source = root.xpath('/application/workflow/node[@id="notebook"]/sources/source',
                                            namespaces={}) 
        
                        el_source[0].text = re.findall('"([^\']*)"', str(cell['source']))[0]
            
                if len(names) != 2:
                    continue 
                                
                if names[0] == 'dict' or names[1] == 'dict':
                    # deal with the alphabetical order
                    if names[1] == 'dict': 
                        names[1] = names[0]
                        names[0] = 'dict'
                    
                    exec(str(cell['source'])) in globals(), locals()
                
                    if 'title' in eval(names[1]).keys() and 'abstract' in eval(names[1]).keys() and 'id' in eval(names[1]).keys():
                    
                        if 'value' in eval(names[1]).keys():
                            # it's a parameter
                            xml_string = '<parameter id="%s" title="%s" abstract="%s" maxOccurs="1" scope="runtime" type="LiteralData">%s</parameter>' % (eval(names[1])['id'], 
                                  eval(names[1])['title'], 
                                  eval(names[1])['abstract'], 
                                  eval(names[1])['value'])
                        
                            el_default_params = root.xpath('/application/jobTemplates/jobTemplate/defaultParameters', 
                                    namespaces={})
                        
                            el_default_params[0].append(etree.fromstring(xml_string))
                     
                        else:
                       
                            # it's the service definition
                            el_workflow = root.xpath('/application/workflow',
                                            namespaces={}) 
        
                            el_workflow[0].attrib['id'] = eval(names[1])['id']
                            el_workflow[0].attrib['title'] = eval(names[1])['title']
                            el_workflow[0].attrib['abstract'] = eval(names[1])['abstract']
                    
            except SyntaxError:
                continue
          
    descriptor = open(descriptor_file, 'wb')
    descriptor.write(etree.tostring(tree, pretty_print=True))
    descriptor.close()


if __name__ == "__main__":
    main(sys.argv[1:])
