/**
	// Terminal application launcher.
	// Executes the &terminal.io.device library's application manager with
	// &terminal.syntax.edit as the target module for the coprocess.
*/
#include <fault/libc.h>
#include <fault/python/environ.h>
#include <unistd.h>
#include <signal.h>
#include <locale.h>

/**
	// The application module is currently unused as &.types.Device
	// covers all of the requirements.
*/
#if 0
static PyMethodDef terminal_module_functions[] = {
	{NULL, NULL, 0, NULL}
};

static PyModuleDef terminal_module_definition = {
	PyModuleDef_HEAD_INIT,
	.m_name = "Terminal",
	.m_methods = terminal_module_functions,
	.m_size = 0
};

static PyObject *
terminal_module_create(void)
{
	PyObject *screen_buffer = NULL;
	struct Device *cmd;
	PyObject *module = PyModule_Create(&terminal_module_definition);

	if (module == NULL)
		return(NULL);

	return(module);

	error:
	{
		Py_DECREF(module);
		return(NULL);
	}
}

static void
__attribute__((constructor))
python_environment_setup()
{
	PyImport_AppendInittab("Terminal", &terminal_module_create);
}
#endif

const char **system_argv = NULL;
int system_argc = -1;

/* &.io.device */
int device_manage_terminal(const char *, void *);
static int coprocess_invocation(void *);
int
main(int argc, const char *argv[])
{
	/*
		// Exit code is wholly controlled by the managing application.
		// The terminal application's exit code is the responsibility of
		// the component that creates it.
	*/
	char *locale_selection = setlocale(LC_ALL, "");

	/* Pass through globals and pick up in coprocess_invocation. */
	system_argc = argc;
	system_argv = argv;

	return(device_manage_terminal(FACTOR_CONTEXT(".", "syntax.edit"), coprocess_invocation));
}

#include <fault/python/bind.h>
#define TARGET_MODULE FACTOR_CONTEXT(".", "syntax.edit")
#define SYSTEM_ENTRY_POINT _coprocess_rewrite
#define FAULT_PYTHON_CONTROL_IMPORTS
#include <fault/python/execute.h>

/*
	// Passed into the managing application; this is called
	// whenever a Device is created that needs servicing by an application.
*/
static int
coprocess_invocation(void *ctx)
{
	int r = 255;
	PyObject *ob;

	r = fault_python_initialize(system_argc, system_argv);
	if (r != 0)
		return(r);

	/*
		// Terminal Application context used to create
		// the &.types.Device instance.
	*/
	{
		PyObj co;
		co = PyCapsule_New(ctx, "sys.terminaldevice", NULL);
		PySys_SetObject("terminaldevice", co);
		Py_DECREF(co);
	}

	r = fault_python_bootstrap_factors();
	if (r != 0)
		goto exit;

	r = fault_python_import_controls(FACTOR_CONTEXT(".", "elements.edit"), "main");
	if (r != 0)
		goto exit;

	ob = fault_python_execute(FACTOR_CONTEXT(".", "elements.edit"), "main");
	r = fault_python_exit_status(ob);

	exit:
	{
		fault_python_close();
	}

	return(r);
}
