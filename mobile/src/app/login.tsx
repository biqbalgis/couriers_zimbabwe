import React from "react";
import { Redirect } from "expo-router";
import { useSession } from "../session";
import { Login } from "../screens/Account";
export default function LoginRoute() {
  const { user } = useSession();
  return user ? <Redirect href="/workspace/dashboard" /> : <Login />;
}
