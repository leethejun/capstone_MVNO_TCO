// Share account resolution between Firebase's observer and the login button.
export function createAccountSession({ getAccount, publish, reportError }) {
  let generation = 0;
  let currentUid = null;
  let pending = null;
  return {
    clear() {
      generation++;
      currentUid = null;
      pending = null;
      publish(null);
      reportError('');
    },
    load(user) {
      if (!user) { this.clear(); return Promise.resolve(null); }
      if (pending && currentUid === user.uid) return pending;
      const attempt = ++generation;
      if (currentUid !== user.uid) publish(null);
      currentUid = user.uid;
      reportError('');
      pending = Promise.resolve().then(getAccount).then(account => {
        if (attempt === generation) publish(account);
        return account;
      }).catch(error => {
        if (attempt === generation) reportError(error.message);
        throw error;
      }).finally(() => {
        if (attempt === generation) pending = null;
      });
      return pending;
    },
  };
}

export async function logoutAccount({ cleanup, signOut, clear, timeoutMs = 5000 }) {
  // Push cleanup is best effort and cannot prevent Firebase logout.
  let timer;
  try {
    await Promise.race([
      Promise.resolve().then(cleanup).catch(() => {}),
      new Promise(resolve => { timer = setTimeout(resolve, timeoutMs); }),
    ]);
  } finally {
    clearTimeout(timer);
  }
  await signOut();
  clear();
}
