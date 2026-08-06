/// @file   logging.cpp
/// @author Enrico Fraccaroli (enrico.fraccaroli@gmail.com)
/// @copyright Copyright (c) 2021 sydelity.net (info@sydelity.com)
/// Distributed under the MIT License (MIT) (See accompanying LICENSE file or
///  copy at http://opensource.org/licenses/MIT)

#include "edacurry/utility/logging.hpp"
#include "pybind11/pybind11.h"

#include <sstream>
#include <cstdarg>
#include <iomanip>
#include <iostream>

// FOREGROUND
#define KRST  "\x1B[0m"
#define KRED  "\x1B[31m"
#define KGRN  "\x1B[32m"
#define KYEL  "\x1B[33m"
#define KBLU  "\x1B[34m"
#define KMAG  "\x1B[35m"
#define KCYN  "\x1B[36m"
#define KWHT  "\x1B[37m"

#define BOLD "\x1B[1m"
#define UNDL "\x1B[4m"

static inline PyObject* get_object(PyObject* module, const std::string& name)
{
	PyObject* object = PyObject_GetAttrString(module, name.c_str());
	if (object == nullptr) {
		PyErr_SetString(PyExc_TypeError, ("Cannot find '" + name + "' in logging module.").c_str());
		return nullptr;
	}
	return object;
}
static inline PyObject* get_method(PyObject* module, const std::string& name)
{
	PyObject* method = PyObject_GetAttrString(module, name.c_str());
	if (method == nullptr) {
		PyErr_SetString(PyExc_TypeError, ("Cannot find '" + name + "' function in logging module.").c_str());
		return nullptr;
	}
	if (!PyCallable_Check(method)) {
		PyErr_SetString(PyExc_TypeError, ("Function '" + name + "' is not callable.").c_str());
		return nullptr;
	}
	return method;
}

namespace logging {

static PyObject* DEBUG, * INFO, * WARNING, * ERROR, * CRITICAL;
static PyObject* isEnabledFor;
static PyObject* debug_fun, * info_fun, * warning_fun, * error_fun, * critical_fun;

///
unsigned int log_level = 0;
///
unsigned int display_flags = 0;

void initialize()
{
	PyObject* logging, * getLogger, * logger;

	if ((logging = PyImport_ImportModule("logging")) == nullptr) {
		PyErr_SetString(PyExc_TypeError, "Cannot find logging module.");
		return;
	}

	if ((getLogger = get_method(logging, "getLogger")) == nullptr) {
		return;
	}

	if ((DEBUG = get_object(logging, "DEBUG")) == nullptr) {
		return;
	}
	if ((INFO = get_object(logging, "INFO")) == nullptr) {
		return;
	}
	if ((WARNING = get_object(logging, "WARNING")) == nullptr) {
		return;
	}
	if ((ERROR = get_object(logging, "ERROR")) == nullptr) {
		return;
	}
	if ((CRITICAL = get_object(logging, "CRITICAL")) == nullptr) {
		return;
	}

	PyObject* logger_args = Py_BuildValue("(s)", "edacurry_logger");
	logger                = PyObject_CallObject(getLogger, logger_args);
	Py_XDECREF(logger_args);
	if (logger == nullptr) {
		PyErr_SetString(PyExc_TypeError, "Cannot create the logger for C++.");
		return;
	}

	if ((isEnabledFor = get_method(logger, "isEnabledFor")) == nullptr) {
		return;
	}

	if ((debug_fun = get_method(logger, "debug")) == nullptr) {
		return;
	}
	if ((info_fun = get_method(logger, "info")) == nullptr) {
		return;
	}
	if ((warning_fun = get_method(logger, "warning")) == nullptr) {
		return;
	}
	if ((error_fun = get_method(logger, "error")) == nullptr) {
		return;
	}
	if ((critical_fun = get_method(logger, "critical")) == nullptr) {
		return;
	}
}

std::string get_simple_date()
{
	static char buffer[32];
	time_t now = time(nullptr);
	strftime(buffer, 32, "%d/%m/%y", localtime(&now));
	return buffer;
}

std::string get_simple_time()
{
	static char buffer[32];
	time_t now = time(nullptr);
	strftime(buffer, 32, "%H:%M", localtime(&now));
	return buffer;
}

bool is_enabled(LogLevel level)
{
	PyObject* args   = Py_BuildValue("(i)", level);
	PyObject* result = PyObject_CallObject(isEnabledFor, args);
	Py_XDECREF(args);
	if (result == nullptr) {
		// Do not leave a pending exception behind: this function has no error
		// channel, so it would surface at an unrelated Python boundary.
		PyErr_Clear();
		return false;
	}
	bool enabled = (PyObject_IsTrue(result) == 1);
	Py_DECREF(result);
	return enabled;
}

void print(char const* file, char const* func, int line, LogLevel level, char const* format, ...)
{
	static size_t current_length = 0;
	static char* buffer = NULL;
	va_list args1;
	va_start(args1, format);
	va_list args2;
	va_copy(args2, args1);
	size_t length = (1UL + std::vsnprintf(NULL, 0, format, args1));
	if (length > current_length) {
		if (buffer == NULL) {
			buffer = static_cast<char*>(std::malloc(sizeof(char) * (length + 1UL)));
		} else {
			buffer = static_cast<char*>(std::realloc(buffer, sizeof(int) * (length + 1UL)));
		}
		current_length = length;
	}
	va_end(args1);
	std::vsnprintf(buffer, length, format, args2);
	va_end(args2);

	// == PREPARE LOG =========================================================
	std::stringstream ss;
	// Add the date and timestamp.
	//ss << "[" << get_simple_date() << " " << get_simple_time() << "]";
	// Add the file:line
	ss << "[" << std::setw(30) << std::left << (std::string(file) + ":" + std::to_string(line)) << "] ";

	// == ACTUALLY LOG ========================================================
	PyObject* log_fun = nullptr;
#if 0
	if (level == LogLevel::DEBUG) {
		ss << KCYN << buffer << KRST;
		log_fun = debug_fun;
	} else if (level == LogLevel::INFO) {
		ss << buffer;
		log_fun = info_fun;
	} else if (level == LogLevel::WARNING) {
		ss << KYEL << buffer << KRST;
		log_fun = warning_fun;
	} else if (level == LogLevel::ERROR) {
		ss << KRED << buffer << KRST;
		log_fun = error_fun;
	} else if (level == LogLevel::CRITICAL) {
		ss << KRED << BOLD << buffer << KRST;
		log_fun = critical_fun;
	}
#else
	if (level == LogLevel::DEBUG) {
		log_fun = debug_fun;
	} else if (level == LogLevel::INFO) {
		log_fun = info_fun;
	} else if (level == LogLevel::WARNING) {
		log_fun = warning_fun;
	} else if (level == LogLevel::ERROR) {
		log_fun = error_fun;
	} else if (level == LogLevel::CRITICAL) {
		log_fun = critical_fun;
	}
	ss << buffer;
#endif

	if (log_fun != nullptr) {
		PyObject* args   = Py_BuildValue("(s)", ss.str().c_str());
		PyObject* result = PyObject_CallObject(log_fun, args);
		Py_XDECREF(args);
		Py_XDECREF(result);
	}

	if ((level == LogLevel::ERROR) || (level == LogLevel::CRITICAL)) {
		throw std::runtime_error("Error encountered!");
	}
}

} // namespace logging
