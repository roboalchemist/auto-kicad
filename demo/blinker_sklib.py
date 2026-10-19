from collections import defaultdict
from skidl import Pin, Part, Alias, SchLib, SKIDL, TEMPLATE

from skidl.pin import pin_types

SKIDL_lib_version = '0.0.1'

blinker = SchLib(tool=SKIDL).add_parts(*[
        Part(**{ 'name':'NE555DR', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'NE555DR'}), 'ref_prefix':'U', 'fplist':['footprints:SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL'], 'footprint':'footprints:SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL', 'keywords':'C7593', 'description':'', 'datasheet':'https://so.szlcsc.com/global.html?c=&k=C9843', 'pins':[
            Pin(num='8',name='VCC',func=pin_types.UNSPEC),
            Pin(num='7',name='DISCH',func=pin_types.UNSPEC),
            Pin(num='6',name='THRES',func=pin_types.UNSPEC),
            Pin(num='5',name='CONT',func=pin_types.UNSPEC),
            Pin(num='4',name='RST',func=pin_types.UNSPEC),
            Pin(num='3',name='OUT',func=pin_types.UNSPEC),
            Pin(num='2',name='TRIG',func=pin_types.UNSPEC),
            Pin(num='1',name='GND',func=pin_types.UNSPEC)], 'unit_defs':[] }),
        Part(**{ 'name':'0805W8F1002T5E', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'0805W8F1002T5E'}), 'ref_prefix':'R', 'fplist':['footprints:R0805'], 'footprint':'footprints:R0805', 'keywords':'C17414', 'description':'', 'datasheet':'https://item.szlcsc.com/142685.html', 'pins':[
            Pin(num='2',name='2',func=pin_types.INPUT),
            Pin(num='1',name='1',func=pin_types.INPUT)], 'unit_defs':[] }),
        Part(**{ 'name':'0805W8F4701T5E', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'0805W8F4701T5E'}), 'ref_prefix':'R', 'fplist':['footprints:R0805'], 'footprint':'footprints:R0805', 'keywords':'C17673', 'description':'', 'datasheet':'https://item.szlcsc.com/142685.html', 'pins':[
            Pin(num='2',name='2',func=pin_types.INPUT),
            Pin(num='1',name='1',func=pin_types.INPUT)], 'unit_defs':[] }),
        Part(**{ 'name':'CL21A106KAYNNNE', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'CL21A106KAYNNNE'}), 'ref_prefix':'C', 'fplist':['footprints:C0805'], 'footprint':'footprints:C0805', 'keywords':'C15850', 'description':'', 'datasheet':'https://item.szlcsc.com/373011.html', 'pins':[
            Pin(num='2',name='2',func=pin_types.UNSPEC),
            Pin(num='1',name='1',func=pin_types.UNSPEC)], 'unit_defs':[] }),
        Part(**{ 'name':'CC0805KRX7R9BB104', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'CC0805KRX7R9BB104'}), 'ref_prefix':'C', 'fplist':['footprints:C0805'], 'footprint':'footprints:C0805', 'keywords':'C49678', 'description':'', 'datasheet':'https://item.szlcsc.com/373011.html', 'pins':[
            Pin(num='2',name='2',func=pin_types.UNSPEC),
            Pin(num='1',name='1',func=pin_types.UNSPEC)], 'unit_defs':[] }),
        Part(**{ 'name':'FC-2012HRK-620D', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'FC-2012HRK-620D'}), 'ref_prefix':'D', 'fplist':['footprints:LED0805-RD'], 'footprint':'footprints:LED0805-RD', 'keywords':'C84256', 'description':'', 'datasheet':'https://item.szlcsc.com/255094.html', 'pins':[
            Pin(num='2',name='+',func=pin_types.UNSPEC),
            Pin(num='1',name='-',func=pin_types.UNSPEC)], 'unit_defs':[] })])