import React, { useState } from "react";
import { View, Text, TextInput, StyleSheet, TouchableOpacity } from "react-native";
import { Controller, Control } from "react-hook-form";
import { Feather } from "@expo/vector-icons";

type Props = {
  control: Control<any>;
  name: string;
  label: string;
  placeholder?: string;
  secureTextEntry?: boolean;
  keyboardType?: "default" | "email-address" | "numeric";
  autoCapitalize?: "none" | "sentences" | "words" | "characters";
};

export default function FormInput({
  control, name, label, placeholder, secureTextEntry, keyboardType="default", autoCapitalize="none",
}: Props) {
  const [show, setShow] = useState(false);
  const isPwd = !!secureTextEntry;

  return (
    <Controller
      control={control}
      name={name}
      render={({ field: { onChange, onBlur, value }, fieldState: { error } }) => (
        <View style={{ marginBottom: 14 }}>
          <Text style={s.label}>{label}</Text>
          <View style={[s.box, !!error && s.boxErr]}>
            <TextInput
              style={s.input}
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              placeholder={placeholder}
              secureTextEntry={isPwd && !show}
              keyboardType={keyboardType}
              autoCapitalize={autoCapitalize}
              autoCorrect={false}
            />
            {isPwd && (
              <TouchableOpacity onPress={() => setShow(v => !v)}>
                <Feather name={show ? "eye-off" : "eye"} size={18} />
              </TouchableOpacity>
            )}
          </View>
          {!!error && <Text style={s.err}>{error.message as string}</Text>}
        </View>
      )}
    />
  );
}

const s = StyleSheet.create({
  label: { marginBottom: 6, color: "#334155", fontWeight: "600" },
  box: {
    borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10, flexDirection: "row", alignItems: "center", gap: 8,
  },
  boxErr: { borderColor: "#ef4444" },
  input: { flex: 1, fontSize: 16 },
  err: { color: "#ef4444", marginTop: 6 },
});
