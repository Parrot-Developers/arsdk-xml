
LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_HOST_MODULE := arsdkgen

arsdkgen_files := \
	arsdkparser.py \
	arsdkgen.py \
	$(call all-files-under,xml,.xml)

# Install files in host staging directory
LOCAL_COPY_FILES := \
	$(foreach __f,$(arsdkgen_files), \
		$(__f):$(HOST_OUT_STAGING)/usr/lib/arsdkgen/$(__f) \
	)

# Needed to force a build order of LOCAL_COPY_FILES
LOCAL_EXPORT_PREREQUISITES := \
	$(foreach __f,$(arsdkgen_files), \
		$(HOST_OUT_STAGING)/usr/lib/arsdkgen/$(__f) \
	)

include $(BUILD_CUSTOM)

###############################################################################
## Custom macro that can be used in LOCAL_CUSTOM_MACROS of a module to
## create automatically rules to generate files from xml.
## Note : in the context of the macro, LOCAL_XXX variables refer to the module
## that use the macro, not this module defining the macro.
## As the content of the macro is 'eval' after, most of variable ref shall be
## escaped (hence the $$). Only $1, $2... variables can be used directly.
## Note : no 'global' variable shall be used except the ones defined by
## alchemy (TARGET_XXX and HOST_XXX variables). Otherwise the macro will no
## work when integrated in a SDK (using local-register-custom-macro).
## Note : rules shoud NOT use any variables defined in the context of the
## macro (for the same reason PRIVATE_XXX variables shall be used in place of
## LOCAL_XXX variables).
## Note : if you need a script or a binary, please install it in host staging
## directory and execute it from there. This way it will also work in the
## context of a SDK.
###############################################################################

# Before arsdkgen is installed, we need it during makefile parsing phase
# We define this variable to find it in $(LOCAL_PATH) if not found yet in
# host staging directory
arsdkgen-macro-path := $(LOCAL_PATH)

# $1: generator filepath
# $2: output directory (Relative to build directory unless an absolute path is
#     given (ex LOCAL_PATH).
# $3: extra parameter passed to the generator.
define arsdkgen-macro

# Setup some internal variables
arsdkgen_python := arsdkgen.py $(if $(call streq,$(V),1),-v)
arsdkgen_generator_path := $1
arsdkgen_module_build_dir := $(call local-get-build-dir)
arsdkgen_out_dir := $(if $(call is-path-absolute,$2),$2,$$(arsdkgen_module_build_dir)/$2)
arsdkgen_done_file := $$(arsdkgen_module_build_dir)/$(LOCAL_MODULE)-arsdkgen.done
$(if $(wildcard $(arsdkgen-macro-path)/arsdkgen.py), \
	arsdkgen_gen_files := $$(shell $(arsdkgen-macro-path)/$$(arsdkgen_python) \
		-f -o $$(arsdkgen_out_dir) $1 -- $(subst $(colon),$(space),$3) || echo FAILED)
	, \
	arsdkgen_gen_files := $$(shell $(HOST_OUT_STAGING)/usr/lib/arsdkgen/$$(arsdkgen_python) \
		-f -o $$(arsdkgen_out_dir) $1 -- $(subst $(colon),$(space),$3) || echo FAILED)
)
$$(if $$(call streq,$$(arsdkgen_gen_files),FAILED),$$(error Failed to list files))

# Create a dependency between generated files and .done file with an empty
# command to make sure regeneration is correctly triggered to files
# depending on them
$$(arsdkgen_gen_files): $$(arsdkgen_done_file)
	$(empty)

# Actual generation rule
# The copy of xml is staging is done in 2 steps because several modules could use
# the same xml the move ensure atomicity of the copy.
$$(arsdkgen_done_file): $(addprefix $(HOST_OUT_STAGING)/usr/lib/arsdkgen/,$(arsdkgen_files))
$$(arsdkgen_done_file): PRIVATE_OUT_DIR := $$(arsdkgen_out_dir)
$$(arsdkgen_done_file): .FORCE
	@echo "$$(PRIVATE_MODULE): Generating arsdk files"
	$(Q) $(HOST_OUT_STAGING)/usr/lib/arsdkgen/$$(arsdkgen_python) \
		-o $$(PRIVATE_OUT_DIR) $1 -- $(subst $(colon),$(space),$3)
	@mkdir -p $$(dir $$@)
	@touch $$@

# Update alchemy variables for the module
LOCAL_CLEAN_FILES += $$(arsdkgen_done_file) $(if $(call is-path-absolute,$2),$(empty),$$(arsdkgen_gen_files))
LOCAL_EXPORT_PREREQUISITES += $$(arsdkgen_gen_files)
LOCAL_PREREQUISITES += $$(arsdkgen_gen_files)
LOCAL_CUSTOM_TARGETS += $$(arsdkgen_done_file)
LOCAL_DEPENDS_HOST_MODULES += host.arsdkgen
LOCAL_C_INCLUDES += $$(arsdkgen_out_dir)
LOCAL_DONE_FILES += $$(notdir $$(arsdkgen_done_file))

endef

# Register the macro in alchemy
$(call local-register-custom-macro,arsdkgen-macro)
