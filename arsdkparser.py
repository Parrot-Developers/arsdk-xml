#!/usr/bin/env python

import os
import pprint
import xml.dom.minidom

_MIN_PROJECT_ID = 0
_MAX_PROJECT_ID = 255
_MIN_FEATURE_ID = 0
_MAX_FEATURE_ID = 255

_MIN_CLASS_ID = 0
_MAX_CLASS_ID = 255

_MIN_CMD_ID = 0
_MAX_CMD_ID = 65535

_FTR_GEN = 'generic'

#===============================================================================
#===============================================================================
class ArParserError(Exception):
    pass

#===============================================================================
#===============================================================================
class ArCmdListType(object):
    NONE = 0
    LIST = 1
    MAP = 2

    TO_STRING = {NONE: "NONE", LIST: "LIST_ITEM", MAP: "MAP_ITEM"}
    FROM_STRING = {"NONE": NONE, "LIST_ITEM": LIST, "MAP_ITEM": MAP}

#===============================================================================
#===============================================================================
class ArCmdBufferType(object):
    NON_ACK = 0
    ACK = 1
    HIGH_PRIO = 2

    TO_STRING = {NON_ACK: "NON_ACK", ACK: "ACK", HIGH_PRIO: "HIGH_PRIO"}
    FROM_STRING = {"NON_ACK": NON_ACK, "ACK": ACK, "HIGH_PRIO": HIGH_PRIO}

#===============================================================================
#===============================================================================
class ArCmdTimeoutPolicy(object):
    POP = 0
    RETRY = 1

    TO_STRING = {POP: "POP", RETRY: "RETRY"}
    FROM_STRING = {"POP": POP, "RETRY": RETRY}

#===============================================================================
#===============================================================================
class ArCmdContent(object):
    UPDATE = 0
    NOTIFICATION = 1

    TO_STRING = {UPDATE: "UPDATE", NOTIFICATION: "NOTIFICATION"}
    FROM_STRING = {"UPDATE": UPDATE, "NOTIFICATION": NOTIFICATION}

#===============================================================================
#===============================================================================
class ArCmdDeprecation(object):

    TO_STRING = {True: "true", False: "false"}
    FROM_STRING = {"true": True, "false": False}

#===============================================================================
#===============================================================================
class ArArgType(object):
    I8 = 0
    U8 = 1
    I16 = 2
    U16 = 3
    I32 = 4
    U32 = 5
    I64 = 6
    U64 = 7
    FLOAT = 8
    DOUBLE = 9
    STRING = 10
    ENUM = 11
    BITFIELD = 12
    MULTISETTING = 13

    TO_STRING = {I8: "i8", U8: "u8", I16: "i16", U16: "u16",
            I32: "i32", U32: "u32", I64: "i64", U64: "u64",
            FLOAT: "float", DOUBLE: "double", STRING: "string",
            ENUM: "enum", BITFIELD: "bitfield", MULTISETTING: "multisetting"}
    FROM_STRING = {"i8": I8, "u8": U8, "i16": I16, "u16": U16,
            "i32": I32, "u32": U32, "i64": I64, "u64": U64,
            "float": FLOAT, "double": DOUBLE, "string": STRING,
            "enum": ENUM, "bitfield": BITFIELD, "multisetting": MULTISETTING}

#===============================================================================
#===============================================================================
class ArParserCtx(object):
    def __init__(self):
        self.projects = []
        self.projectsById = {}
        self.projectsByName = {}
        self.features = []
        self.featuresById = {}
        self.featuresByName = {}

    def walk_classes(self):
        for projectObj in self.projects:
            for classObj in projectObj.classes:
                yield (projectObj, classObj)

    def walk_cmds(self):
        for projectObj in self.projects:
            for classObj in projectObj.classes:
                for cmdObj in classObj.cmds:
                    yield (projectObj, classObj, cmdObj)

    def walk_msgs(self):
        for featureObj in self.features:
            for msg in featureObj.getMsgs():
                yield (featureObj, msg)

#===============================================================================
#===============================================================================
class ArProject(object):
    def __init__(self, name, projectId, doc):
        self.name = name
        self.projectId = projectId
        self.doc = doc
        self.classes = []
        self.classesById = {}
        self.classesByName = {}

    def __repr__(self):
        return ("{name='%s', projectId=%d, doc='%s', classes=%s}" % (
                self.name,
                self.projectId,
                repr(self.doc),
                pprint.pformat(self.classes)))

#===============================================================================
#===============================================================================
class ArFeature(object):
    def __init__(self, name, featureId, doc):
        self.name = name
        self.featureId = featureId
        self.doc = doc
        self.enums = []
        self.enumsByName = {}
        self.multisets = []
        self.multisetsByName = {}
        self.cmds = []
        self.cmdsById = {} #only for real feature, empty for project
        self.cmdsByName = {} #only for real feature, empty for project
        self.evts = []
        self.evtsById = {}
        self.evtsByName = {}
        self.classes = None #only for project conversion
        self.classesById = {} #only for project conversion
        self.classesByName = {} #only for project conversion

    def getMsgs (self):
        return  self.cmds + self.evts

    def getMsgsById (self):
        #only for feature
        return dict(self.cmdsById, **self.evtsById)

    def getMsgsByName (self):
        #only for feature
        return dict(self.cmdsByName, **self.evtsByName)

    def __repr__(self):
        return ("{name='%s', featureId=%d, doc='%s', enums='%s', "
                "multisets='%s', cmds='%s', evts='%s'}" % (
                self.name,
                self.featureId,
                repr(self.doc),
                pprint.pformat(self.enums),
                pprint.pformat(self.multisets),
                pprint.pformat(self.cmds),
                pprint.pformat(self.evts)))

    @staticmethod
    def from_project(prj):
        ftrObj = ArFeature (prj.name, prj.projectId, prj.doc)
        ftrObj.classes = prj.classes
        ftrObj.classesById = prj.classesById
        ftrObj.classesByName = prj.classesByName

        for cl in prj.classes:
            for cmd in cl.cmds:
                msgId = cmd.cmdId
                msgName = cmd.name
                if "event" in cl.name.lower() or "state" in cl.name.lower():
                    msgObj = ArEvt(msgName, msgId, cmd.doc, cmd.listType,
                            cmd.bufferType, cmd.timeoutPolicy, cmd.content,
                            cmd.isDeprecated, ftrObj)
                else:
                    msgObj = ArCmd(msgName, msgId, cmd.doc, cmd.listType,
                            cmd.bufferType, cmd.timeoutPolicy, cmd.content,
                            cmd.isDeprecated, ftrObj)

                if cmd.listType == ArCmdListType.MAP:
                    msgObj.mapKey = cmd.args[0]
                msgObj.cls = cl

                msgObj.args = cmd.args
                msgObj.argsByName = cmd.argsByName
                # Create enums
                for arg in msgObj.args:
                    if len(arg.enums) > 0:
                        enumName = cl.name + '_' +\
                                cmd.name[0].upper()+cmd.name[1:]+'_' +\
                                arg.name[0].upper()+arg.name[1:]
                        enumObj = ArEnum(enumName, arg.doc)
                        enumObj.msg = msgObj
                        for val in arg.enums:
                            eValObj = ArEnumValue(val.name, val.value, val.doc)
                            enumObj.values.append(eValObj)
                            enumObj.valuesByName[val.name] = eValObj
                        ftrObj.enums.append(enumObj)
                        ftrObj.enumsByName[enumName] = enumObj
                        arg.argType = enumObj
                        arg.doc = ''

                if isinstance(msgObj, ArCmd):
                    ftrObj.cmds.append(msgObj)
                else:
                    ftrObj.evts.append(msgObj)
        return ftrObj

#===============================================================================
#===============================================================================
class ArClass(object):
    def __init__(self, name, classId, doc):
        self.name = name
        self.classId = classId
        self.doc = doc
        self.cmds = []
        self.cmdsById = {}
        self.cmdsByName = {}

    def __repr__(self):
        return ("{name='%s', classId=%d, doc='%s', cmds=%s}" % (
                self.name,
                self.classId,
                repr(self.doc),
                pprint.pformat(self.cmds)))

#===============================================================================
#===============================================================================
class ArMsg(object):
    def __init__(self, name, cmdId, doc, listType, bufferType, timeoutPolicy,
            content, isDeprecated, ftr):
        self.name = name
        self.cmdId = cmdId
        self.doc = doc
        self.listType = listType
        self.bufferType = bufferType
        self.timeoutPolicy = timeoutPolicy
        self.content = content
        self.mapKey = None
        self.args = []
        self.argsByName = {}
        self.cls = None #only for project conversion
        self.isDeprecated = isDeprecated
        self.ftr = ftr

    def __repr__(self):
        return ("{name='%s', cmdId=%d, doc='%s', listType='%s', "
                "bufferType='%s', timeoutPolicy='%s', content='%s', "
                "args=%s isDeprecated=%r}" % (
                self.name,
                self.cmdId,
                repr(self.doc),
                ArCmdListType.TO_STRING[self.listType],
                ArCmdBufferType.TO_STRING[self.bufferType],
                ArCmdTimeoutPolicy.TO_STRING[self.timeoutPolicy],
                ArCmdContent.TO_STRING[self.content],
                pprint.pformat(self.args),
                self.isDeprecated))

#===============================================================================
#===============================================================================
class ArCmd(ArMsg):
    def __init__(self, name, cmdId, doc, listType, bufferType, timeoutPolicy,
            content, isDeprecated, ftr):
        ArMsg.__init__(self, name, cmdId, doc, listType, bufferType,
                    timeoutPolicy, content, isDeprecated, ftr)

#===============================================================================
#===============================================================================
class ArEvt(ArMsg):
    def __init__(self, name, cmdId, doc, listType, bufferType, timeoutPolicy,
            content, isDeprecated, ftr):
        ArMsg.__init__(self, name, cmdId, doc, listType, bufferType,
                    timeoutPolicy, content, isDeprecated, ftr)

#===============================================================================
#===============================================================================
class ArComment(object):
    def __init__(self, title, desc, support, triggered, result):
        self.title = title
        self.desc = desc
        self.support = support
        self.triggered = triggered
        self.result = result

    def __repr__(self):
        return ("{title='%s', desc=%s, support='%s', triggered='%s', "
                "result='%s'}" % (
                self.title,
                self.desc,
                self.support,
                self.triggered,
                self.result))

#===============================================================================
#===============================================================================
class ArArg(object):
    def __init__(self, name, argType, doc):
        self.name = name
        self.argType = argType
        self.doc = doc
        self.enums = []
        self.enumsByName = {}

    def __repr__(self):
        if isinstance(self.argType, str):
            argTypeRep = ArArgType.TO_STRING[self.argType]
        else:
            argTypeRep = pprint.pformat(self.argType)

        return ("{name='%s', argType='%s', doc='%s', enums=%s}" % (
                self.name,
                argTypeRep,
                repr(self.doc),
                pprint.pformat(self.enums)))

#===============================================================================
#===============================================================================
class ArMultiSetting(object):
    def __init__(self, name, doc):
        self.name = name
        self.doc = doc
        self.links = []
        self.msgs = []

    def __repr__(self):
        return ("{name='%s', doc='%s', msgs=%s}" % (
                self.name,
                repr(self.doc),
                pprint.pformat(self.msgs)))

#===============================================================================
#===============================================================================
class ArEnumValue(object):
    def __init__(self, name, value, doc):
        self.name = name
        self.doc = doc
        self.value = value

    def __cmp__(self, other):
        return cmp(self.value, other.value)

    def __repr__(self):
        return ("{name='%s', value=%d, doc='%s'}" % (
                self.name,
                self.value,
                repr(self.doc)))

#===============================================================================
#===============================================================================
class ArEnum(object):
    def __init__(self, name, doc):
        self.name = name
        self.doc = doc
        self.values = []
        self.valuesByName = {}
        self.usedLikeBitfield = False
        self.msg = None #only for project conversion

    def getMaxBitfieldVal(self):
        return 2 ** max(self.values).value

    def __repr__(self):
        return ("{name='%s', doc='%s', values='%s'}" % (
                self.name,
                repr(self.doc),
                pprint.pformat(self.values)))

#===============================================================================
#===============================================================================
class ArBitfield(object):
    TYPE_TO_LENGTH = {ArArgType.U8:2**7, ArArgType.U16:2**15, ArArgType.U32:2**31, ArArgType.U64:2**63}

    def __init__(self, enum, btfType):
        self.enum = enum
        self.btfType = btfType

    def __repr__(self):
        return ("{enum='%s', type='%s'}" % (
                pprint.pformat(self.enum),
                pprint.pformat(self.btfType)))

#===============================================================================
#===============================================================================
def _get_node_content(node):
    try:
        content = node.childNodes[0].nodeValue.strip()
        lines = [l.strip() for l in content.split('\n')]
        return '\n'.join(lines)
    except:
        return ''

#===============================================================================
#===============================================================================
def _parse_project_node(filePath, projectNode, projectObj):
    for classNode in projectNode.getElementsByTagName("class"):
        className = classNode.getAttribute("name")
        classId = int(classNode.getAttribute("id"))
        classDoc = _get_node_content(classNode).strip()

        # Check class id/name
        if classId in projectObj.classesById:
            raise ArParserError("%s: Duplicate class id %d" % (
                    filePath, classId))
        if className in projectObj.classesByName:
            raise ArParserError("%s: Duplicate class name '%s'" % (
                    filePath, className))
        if classId < _MIN_CLASS_ID or classId > _MAX_CLASS_ID:
            raise ArParserError("%s: Invalid class id %d" % (
                    filePath, classId))

        # Create class object
        classObj = ArClass(className, classId, classDoc)
        projectObj.classes.append(classObj)
        projectObj.classesById[classId] = classObj
        projectObj.classesByName[className] = classObj

        # Parse class node
        _parse_class_node(filePath, classNode, classObj)

#===============================================================================
#===============================================================================
def _parse_feature_node(ctx, filePath, featureNode, featureObj):

    for enumsNode in featureNode.getElementsByTagName("enums"):
        for enumNode in enumsNode.getElementsByTagName("enum"):
            enumName = enumNode.getAttribute("name")
            enumDoc = _get_node_content(enumNode).strip()

            # Check enum name
            if enumName in featureObj.enumsByName:
                raise ArParserError("%s: Duplicate enum name '%s'" % (
                        filePath, enumName))

            # Create enum object
            enumObj = ArEnum(enumName, enumDoc)
            featureObj.enums.append(enumObj)
            featureObj.enumsByName[enumName] = enumObj

            # Parse enum node
            _parse_enum_node(filePath, enumNode, enumObj)

    _parse_feature_node_multisets(ctx, filePath, featureNode, featureObj)

    _parse_feature_node_msgs(ctx, filePath, featureNode, featureObj)

#===============================================================================
#===============================================================================
def _parse_feature_node_multisets(ctx, filePath, featureNode, featureObj):
    for multisetsNode in featureNode.getElementsByTagName("multisettings"):
        for multisetNode in multisetsNode.getElementsByTagName("multisetting"):
            multisetName = multisetNode.getAttribute("name")
            multisetDoc = _get_node_content(multisetNode).strip()

            # Check multiset name
            if multisetName in featureObj.multisetsByName:
                raise ArParserError("%s: Duplicate multiset name '%s'" % (
                        filePath, multisetName))

            # Create multiset object
            multisetObj = ArMultiSetting(multisetName, multisetDoc)
            featureObj.multisets.append(multisetObj)
            featureObj.multisetsByName[multisetName] = multisetObj

            # Parse multiset node
            _parse_multiset_node(filePath, multisetNode, multisetObj)

#===============================================================================
#===============================================================================
def _parse_multiset_node(filePath, multisetNode, multisetObj):
    for memberNode in multisetNode.getElementsByTagName("member"):
        multisetObj.links.append(memberNode.getAttribute("link"))

#===============================================================================
#===============================================================================
def _parse_feature_node_msgs(ctx, filePath, featureNode, featureObj):

    for msgsNode in featureNode.getElementsByTagName("msgs"):
        for msgNode in msgsNode.getElementsByTagName("cmd") + \
                msgsNode.getElementsByTagName("evt"):
            msgName = msgNode.getAttribute("name")
            msgId = int(msgNode.getAttribute("id"))
            msgDoc = _get_node_content(msgNode).strip()

            if msgId < _MIN_CMD_ID or msgId > _MAX_CMD_ID:
                raise ArParserError("%s: Invalid msg id %d" % (
                        filePath, msgId))

            # Check msg name
            if msgName in featureObj.getMsgsByName():
                raise ArParserError("%s: Duplicate message name '%s'" % (
                        filePath, msgName))

            # Check msg id
            if msgId in featureObj.getMsgsById():
                raise ArParserError("%s: Duplicate message id '%s'" % (
                        filePath, msgName))

            # Get type
            msgType = ArCmdListType.NONE
            mapKey = None
            if msgNode.hasAttribute("type"):
                attr, _, mapKey = msgNode.getAttribute("type").partition(':')

                if attr not in ArCmdListType.FROM_STRING:
                    raise ArParserError("%s: Invalid list type '%s'" % (
                            filePath, attr))
                msgType = ArCmdListType.FROM_STRING[attr]

            # Get buffer type
            msgBufferType = ArCmdBufferType.ACK
            if msgNode.hasAttribute("buffer"):
                attr = msgNode.getAttribute("buffer")
                if attr not in ArCmdBufferType.FROM_STRING:
                    raise ArParserError("%s: Invalid buffer type '%s'" % (
                            filePath, attr))
                msgBufferType = ArCmdBufferType.FROM_STRING[attr]

            # Get timeout policy
            msgTimeoutPolicy = ArCmdTimeoutPolicy.POP
            if msgNode.hasAttribute("timeout"):
                attr = msgNode.getAttribute("timeout")
                if attr not in ArCmdTimeoutPolicy.FROM_STRING:
                    raise ArParserError("%s: Invalid timout policy '%s'" % (
                            filePath, attr))
                msgTimeoutPolicy = ArCmdTimeoutPolicy.FROM_STRING[attr]

            # Get Content
            msgContent = ArCmdContent.UPDATE
            if msgNode.hasAttribute("content"):
                attr = msgNode.getAttribute("content")
                if attr not in ArCmdContent.FROM_STRING:
                    raise ArParserError("%s: Invalid notification '%s'" % (
                            filePath, attr))
                msgContent = ArCmdContent.FROM_STRING[attr]

            # Get if the message is deprecated
            mgsIsDeprecated = False
            if msgNode.hasAttribute("deprecated"):
                attr = msgNode.getAttribute("deprecated")
                if attr not in ArCmdDeprecation.FROM_STRING:
                    mgsIsDeprecated = ArCmdDeprecation.FROM_STRING[attr]

            # Create msg object
            if msgNode in msgsNode.getElementsByTagName("cmd"):
                #is command
                msgObj = ArCmd (msgName, msgId, msgDoc,
                        msgType, msgBufferType, msgTimeoutPolicy, msgContent,
                        mgsIsDeprecated, featureObj)

            else:
                #is event
                msgObj = ArEvt(msgName, msgId, msgDoc,
                        msgType, msgBufferType, msgTimeoutPolicy, msgContent,
                        mgsIsDeprecated, featureObj)

            # Parse msg node
            _parse_msg_node(ctx, filePath, featureObj, msgNode, msgObj)

            # Find map key
            if mapKey :
                if mapKey not in msgObj.argsByName:
                    raise ArParserError("%s: Invalid Map Key '%s'" % (
                            filePath, mapKey))
                msgObj.mapKey = msgObj.argsByName[mapKey]

            if isinstance(msgObj, ArCmd):
                featureObj.cmds.append(msgObj)
                featureObj.cmdsById[msgId] = msgObj
                featureObj.cmdsByName[msgName] = msgObj
            else:
                featureObj.evts.append(msgObj)
                featureObj.evtsById[msgId] = msgObj
                featureObj.evtsByName[msgName] = msgObj

#===============================================================================
#===============================================================================
def _parse_class_node(filePath, classNode, classObj):
    for cmdNode in classNode.getElementsByTagName("cmd"):
        cmdName = cmdNode.getAttribute("name")
        cmdId = int(cmdNode.getAttribute("id"))
        cmdDoc = _get_cmt_node(cmdNode)

        if cmdId < _MIN_CMD_ID or cmdId > _MAX_CMD_ID:
            raise ArParserError("%s: Invalid cmd id %d" % (
                    filePath, cmdId))

        # Get list type
        cmdListType = ArCmdListType.NONE
        if cmdNode.hasAttribute("type"):
            attr = cmdNode.getAttribute("type")
            if attr not in ArCmdListType.FROM_STRING:
                raise ArParserError("%s: Invalid list type '%s'" % (
                        filePath, attr))
            cmdListType = ArCmdListType.FROM_STRING[attr]

        # Get buffer type
        cmdBufferType = ArCmdBufferType.ACK
        if cmdNode.hasAttribute("buffer"):
            attr = cmdNode.getAttribute("buffer")
            if attr not in ArCmdBufferType.FROM_STRING:
                raise ArParserError("%s: Invalid buffer type '%s'" % (
                        filePath, attr))
            cmdBufferType = ArCmdBufferType.FROM_STRING[attr]

        # Get timeout policy
        cmdTimeoutPolicy = ArCmdTimeoutPolicy.POP
        if cmdNode.hasAttribute("timeout"):
            attr = cmdNode.getAttribute("timeout")
            if attr not in ArCmdTimeoutPolicy.FROM_STRING:
                raise ArParserError("%s: Invalid timout policy '%s'" % (
                        filePath, attr))
            cmdTimeoutPolicy = ArCmdTimeoutPolicy.FROM_STRING[attr]

        # Check cmd name
        if cmdName in classObj.cmdsByName:
            raise ArParserError("%s: Duplicate cmd name '%s'" % (
                    filePath, cmdName))

        # Get cmd Content
        cmdContent = ArCmdContent.UPDATE
        if cmdNode.hasAttribute("content"):
            attr = cmdNode.getAttribute("content")
            if attr not in ArCmdContent.FROM_STRING:
                raise ArParserError("%s: Invalid notification '%s'" % (
                        filePath, attr))
            cmdContent = ArCmdContent.FROM_STRING[attr]

        # Get if the message is deprecated
        mgsIsDeprecated = False
        if cmdNode.hasAttribute("deprecated"):
            attr = cmdNode.getAttribute("deprecated")
            if attr == "true":
                mgsIsDeprecated = True

        # Create cmd object
        cmdObj = ArCmd(cmdName, cmdId, cmdDoc, cmdListType, cmdBufferType,
                    cmdTimeoutPolicy, cmdContent, mgsIsDeprecated, None)
        cmdObj.cls = classObj
        classObj.cmds.append(cmdObj)
        classObj.cmdsById[cmdId] = cmdObj
        classObj.cmdsByName[cmdName] = cmdObj

        # Parse cmd node
        _parse_prj_cmd_node(filePath, cmdNode, cmdObj)

#===============================================================================
#===============================================================================
def _parse_prj_cmd_node(filePath, cmdNode, cmdObj):
    for argNode in cmdNode.getElementsByTagName("arg"):
        argName = argNode.getAttribute("name")
        argDoc = _get_node_content(argNode).strip()

        # Arg type
        attr = argNode.getAttribute("type")
        if attr not in ArArgType.FROM_STRING:
            raise ArParserError("%s: Invalid arg type '%s'" % (
                    filePath, attr))
        argType = ArArgType.FROM_STRING[attr]

        # Check arg name
        if argName in cmdObj.argsByName:
            raise ArParserError("%s: Duplicate arg name '%s'" % (
                    filePath, argName))

        # Create arg object
        argObj = ArArg(argName, argType, argDoc)
        cmdObj.args.append(argObj)
        cmdObj.argsByName[argName] = argObj

        # Parse arg node
        _parse_arg_node(filePath, argNode, argObj)

def _fmt_cmt_node(raw_cmt):
    one_line = ' '.join(raw_cmt.split())
    lines = [l.strip() for l in one_line.split(r'\n')]
    res = '\n'.join(lines)
    return res

def _get_cmt_node(msgNode):
    if msgNode.getElementsByTagName("comment"):
        commentNode = msgNode.getElementsByTagName("comment")[0]
        cmtTitle = commentNode.getAttribute("title")
        cmtSupport = commentNode.getAttribute("support")

        cmtDesc = _fmt_cmt_node(commentNode.getAttribute("desc"))

        if commentNode.hasAttribute("triggered"):
            cmtTriggered = _fmt_cmt_node(commentNode.getAttribute("triggered"))
        else:
            cmtTriggered = None

        if commentNode.hasAttribute("result"):
            cmtResult = _fmt_cmt_node(commentNode.getAttribute("result"))
        else:
            cmtResult = None

        # Create comment object
        return ArComment(cmtTitle, cmtDesc, cmtSupport,
                cmtTriggered, cmtResult)
    else:
        oldComment = _get_node_content(msgNode)
        return ArComment(oldComment.splitlines()[0], oldComment, None,
                None, None)

#===============================================================================
#===============================================================================
def _parse_msg_node(ctx, filePath, ftr, msgNode, msgObj):
    if msgNode.getElementsByTagName("comment"):
        commentNode = msgNode.getElementsByTagName("comment")[0]
        cmtTitle = commentNode.getAttribute("title")
        cmtSupport = commentNode.getAttribute("support")

        cmtDesc = _fmt_cmt_node(commentNode.getAttribute("desc"))

        if commentNode.hasAttribute("triggered"):
            cmtTriggered = _fmt_cmt_node(commentNode.getAttribute("triggered"))
        else:
            cmtTriggered = None

        if commentNode.hasAttribute("result"):
            cmtResult = _fmt_cmt_node(commentNode.getAttribute("result"))
        else:
            cmtResult = None

        # Create comment object
        msgObj.doc = ArComment(cmtTitle, cmtDesc, cmtSupport,
                cmtTriggered, cmtResult)
    else:
        oldComment = _get_node_content(msgNode)
        msgObj.doc = ArComment(oldComment.splitlines()[0], oldComment, None,
                None, None)

    _parse_msg_node_args(ctx, filePath, ftr, msgNode, msgObj)

#===============================================================================
#===============================================================================
def _parse_msg_node_args(ctx, filePath, ftr, msgNode, msgObj):
    for argNode in msgNode.getElementsByTagName("arg"):
        argName = argNode.getAttribute("name")
        argDoc = _get_node_content(argNode).strip()

        # Get type attrs
        attr1, _, flw = argNode.getAttribute("type").partition(':')
        attr2, _, attr3 = flw.partition(':')
        # Check arg type
        if attr1 not in ArArgType.FROM_STRING:
            raise ArParserError("%s: Invalid arg type '%s'" % (
                    filePath, attr1))

        if ArArgType.FROM_STRING[attr1] == ArArgType.ENUM:
            # Find Enum
            if attr2 not in ftr.enumsByName and \
                    (_FTR_GEN not in ctx.featuresByName or \
                    attr2 not in ctx.featuresByName[_FTR_GEN].enumsByName):
                raise ArParserError("%s: Invalid enum arg type '%s'" % (
                    filePath, attr2))

            if attr2 in ftr.enumsByName:
                argType = ftr.enumsByName[attr2]
            else:
                argType = ctx.featuresByName[_FTR_GEN].enumsByName[attr2]

        elif ArArgType.FROM_STRING[attr1] == ArArgType.BITFIELD:
            # Find Enum
            if attr3 not in ftr.enumsByName and \
                    (_FTR_GEN not in ctx.featuresByName or \
                    attr3 not in ctx.featuresByName[_FTR_GEN].enumsByName):
                raise ArParserError("%s: Invalid bitfield enum arg type '%s'"
                        % (filePath, attr3))

            # Check bitfield length
            if attr2 not in ArArgType.FROM_STRING and \
                    ArArgType.FROM_STRING[attr2] in ArBitfield.TYPE_TO_LENGTH:
                raise ArParserError("%s: Invalid bitfield enum arg length '%s'"
                        % (filePath, attr2))

            if attr3 in ftr.enumsByName:
                btfEnum = ftr.enumsByName[attr3]
            else:
                btfEnum = ctx.featuresByName[_FTR_GEN].enumsByName[attr3]
            btfType = ArArgType.FROM_STRING[attr2]

            # Check Compatibility between Enum max value and bitfield length
            if ArBitfield.TYPE_TO_LENGTH[btfType] < btfEnum.getMaxBitfieldVal():
                raise ArParserError("%s: Too Small bitfield length '%s.%s'"
                        % (filePath, msgObj.name, argName))

            argType = ArBitfield(btfEnum, btfType)
            btfEnum.usedLikeBitfield = True
        elif ArArgType.FROM_STRING[attr1] == ArArgType.MULTISETTING:
            # Find multi setting
            if attr2 not in ftr.multisetsByName and \
                    (_FTR_GEN not in ctx.featuresByName or \
                    attr2 not in ctx.featuresByName[_FTR_GEN].multisetsByName):
                raise ArParserError("%s: Invalid multisetting arg type '%s'"
                        % (filePath, attr2))

            if attr2 in ftr.multisetsByName:
                argType = ftr.multisetsByName[attr2]
            else:
                argType = ctx.featuresByName[_FTR_GEN].multisetsByName[attr2]
        else:
            argType = ArArgType.FROM_STRING[attr1]

        # Check arg name
        if argName in msgObj.argsByName:
            raise ArParserError("%s: Duplicate arg name '%s'" % (
                    filePath, argName))

        # Create arg object
        argObj = ArArg(argName, argType, argDoc)
        msgObj.args.append(argObj)
        msgObj.argsByName[argName] = argObj

        # Parse arg node
        _parse_arg_node(filePath, argNode, argObj)

#===============================================================================
#===============================================================================
def _parse_arg_node(filePath, argNode, argObj):
    nextValue = 0
    for enumNode in argNode.getElementsByTagName("enum"):
        enumName = enumNode.getAttribute("name")
        enumDoc = _get_node_content(enumNode).strip()

        enumValue = nextValue
        nextValue += 1

        # Check enum name
        if enumName in argObj.enumsByName:
            raise ArParserError("%s: Duplicate enum name '%s'" % (
                    filePath, enumName))

        # Create enum object
        enumObj = ArEnumValue(enumName, enumValue, enumDoc)
        argObj.enums.append(enumObj)
        argObj.enumsByName[enumName] = enumObj

#===============================================================================
#===============================================================================
def _parse_enum_node(filePath, enumNode, enumObj):
    nextValue = 0
    for eValNode in enumNode.getElementsByTagName("value"):
        eValName = eValNode.getAttribute("name")
        eValDoc = _get_node_content(eValNode).strip()

        if eValNode.hasAttribute("val"):
            eValVal = int(eValNode.getAttribute("val"))
        else:
            eValVal = nextValue
            nextValue += 1
        nextValue = eValVal + 1

        # Check enum value name
        if eValName in enumObj.valuesByName:
            raise ArParserError("%s: Duplicate enum value name '%s'" % (
                    filePath, eValName))

        # Create enum value object
        eValObj = ArEnumValue(eValName, eValVal, eValDoc)
        enumObj.values.append(eValObj)
        enumObj.valuesByName[eValName] = eValObj

#===============================================================================
#===============================================================================
def parse_prj_xml(ctx, filePath):
    # Parse project xml file
    try:
        xmlDom = xml.dom.minidom.parse(filePath)
    except Exception as ex:
        raise ArParserError("Error while loading '%s': %s" % (
                filePath, str(ex)))

    # Get project node
    projectNode = xmlDom.documentElement
    if projectNode.tagName != "project":
        raise ArParserError("%s: Bad root element: '%s'" % (
                filePath, projectNode.tagName))
    projectName = projectNode.getAttribute("name")
    projectId = int(projectNode.getAttribute("id"))
    projectDoc = _get_node_content(projectNode).strip()

    # Check project id/name
    if projectId in ctx.projectsById:
        raise ArParserError("%s: Duplicate project id %d" % (
                filePath, projectId))
    if projectId < _MIN_PROJECT_ID or projectId > _MAX_PROJECT_ID:
        raise ArParserError("%s: Invalid project id %d" % (
                filePath, projectId))
    if projectName in ctx.projectsByName:
        raise ArParserError("%s: Duplicate project name '%s'" % (
                filePath, projectName))

    # Create project object
    projectObj = ArProject(projectName, projectId, projectDoc)
    ctx.projects.append(projectObj)
    ctx.projectsById[projectId] = projectObj
    ctx.projectsByName[projectName] = projectObj

    # Parse project node
    _parse_project_node(filePath, projectNode, projectObj)

    # Convert project to feature object
    featureObj = ArFeature.from_project(projectObj)
    ctx.features.append(featureObj)
    ctx.featuresById[featureObj.featureId] = featureObj
    ctx.featuresByName[featureObj.name] = featureObj

#===============================================================================
#===============================================================================
def parse_ftr_xml(ctx, filePath):
    # Parse feature xml file
    try:
        xmlDom = xml.dom.minidom.parse(filePath)
    except Exception as ex:
        raise ArParserError("Error while loading '%s': %s" % (
                filePath, str(ex)))

    # Get feature node
    featureNode = xmlDom.documentElement
    if featureNode.tagName != "feature":
        raise ArParserError("%s: Bad root element: '%s'" % (
                filePath, featureNode.tagName))
    featureName = featureNode.getAttribute("name")
    featureId = int(featureNode.getAttribute("id"))
    featureDoc = _get_node_content(featureNode).strip()

    # Check feature id/name
    if featureId in ctx.featuresById:
        raise ArParserError("%s: Duplicate feature id %d" % (
                filePath, featureId))
    if featureId < _MIN_FEATURE_ID or featureId > _MAX_FEATURE_ID:
        raise ArParserError("%s: Invalid feature id %d" % (
                filePath, featureId))
    if featureName in ctx.featuresByName:
        raise ArParserError("%s: Duplicate feature name '%s'" % (
                filePath, featureName))

    # Create feature object
    featureObj = ArFeature(featureName, featureId, featureDoc)
    ctx.features.append(featureObj)
    ctx.featuresById[featureId] = featureObj
    ctx.featuresByName[featureName] = featureObj

    # Parse feature node
    _parse_feature_node(ctx, filePath, featureNode, featureObj)

#===============================================================================
#===============================================================================
def _link_to_msg(ctx, link):
    parts = link.split(".")

    if len(parts) < 2:
        return None

    if not parts[0] in ctx.featuresByName:
        return None
    ftr = ctx.featuresByName[parts[0]]

    if len(parts) == 2:
        return ftr.getMsgsByName[parts[1]]

    # Project part
    clsName = parts[1]
    cmdName = parts[2]

    for cmd in ftr.cmds + ftr.evts:
        if cmd.name == cmdName and cmd.cls and cmd.cls.name == clsName:
            return cmd

    return None

#===============================================================================
#===============================================================================
def finalize_ftrs(ctx):
    # Finalize features
    for ftr in ctx.features:
        # Finalize multi settings
        for multiset in ftr.multisets:
            for link in multiset.links:
                msg = _link_to_msg(ctx, link)
                if not msg:
                    raise ArParserError("%s: Bad multisetting link '%s'" % (
                            filePath, link))
                multiset.msgs.append(msg)

#===============================================================================
#===============================================================================
def parse_xml(ctx, filePath):
    # Parse xml file
    try:
        xmlDom = xml.dom.minidom.parse(filePath)
    except Exception as ex:
        raise ArParserError("Error while loading '%s': %s" % (
                filePath, str(ex)))

    # Get feature node
    node = xmlDom.documentElement
    if node.tagName == "feature":
        parse_ftr_xml(ctx, filePath)
    elif node.tagName == "project":
        parse_prj_xml(ctx, filePath)

#===============================================================================
#===============================================================================
def main():
    ctx = ArParserCtx()
    path, filename = os.path.split(os.path.realpath(__file__))
    path = os.path.join(path, "xml")

    # first load generic.xml
    parse_xml(ctx, os.path.join(path, "generic.xml"))
    for f in sorted(os.listdir(path)):
        if not f.endswith(".xml") or f == "generic.xml":
            continue
        parse_xml(ctx, os.path.join(path, f))

    # Finalize MultiSettings
    finalize_ftrs(ctx)

    #for prj in ctx.projects:
    #    print prj
    #    print '\n'
    #for f in ctx.features:
    #    print f
    #    print '\n'

#===============================================================================
#===============================================================================
if __name__ == "__main__":
    main()
